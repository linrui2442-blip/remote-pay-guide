"""Real SQLite post-commit revocation; fake provider and network tripwires."""
import gc
import json
import socket
import sqlite3
from unittest.mock import patch

import g4b_github_production_line_smoke as base
from production.runtime import orchestrator as runtime
from orchestration.production import claim_authorized_production_execution


def sql(statement, args=()):
    db = sqlite3.connect(base.fixture.DB)
    try:
        rows = db.execute(statement, args).fetchall()
        db.commit()
        return rows
    finally:
        db.close()


def main():
    base.init_results_table()
    cases = ('normal', 'kill', 'autonomy', 'policy', 'revision', 'runtime_state',
             'intent_owner', 'runtime_input', 'task_state', 'task_payload',
             'route', 'terminal', 'duplicate_result', 'duplicate_job')
    for case in cases:
        base.fixture._enable()
        pid = base.fixture._create('post-intent-' + case)
        base.prepare_authorized_production(pid)
        claimed = claim_authorized_production_execution(pid)
        jid, tid = claimed['runtime_job']['id'], claimed['production_task'].id
        client = base.FakeGitHubClient()
        committed = []

        def after_commit():
            # Independent connection sees intent and can acquire a write lock.
            db = sqlite3.connect(base.fixture.DB, timeout=1)
            try:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT execution_state,execution_metadata FROM runtime_jobs WHERE id=?', (jid,)).fetchone()
                assert row[0] == 'dispatch_intent'
                assert json.loads(row[1])['runtime_job_id'] == jid
                committed.append(row)
                db.rollback()
            finally:
                db.close()
            if case == 'kill': base.autonomy.update_autonomy_settings(kill_switch_active=True)
            if case == 'autonomy': base.autonomy.update_autonomy_settings(autonomy_enabled=False)
            if case == 'policy': sql("UPDATE intelligence_policy_decisions SET decision='BLOCK' WHERE content_plan_id=?", (pid,))
            if case == 'revision': sql('UPDATE intelligence_content_plans SET revision=revision+1 WHERE id=?', (pid,))
            if case == 'runtime_state': sql("UPDATE runtime_jobs SET status='failed' WHERE id=?", (jid,))
            if case == 'intent_owner':
                changed = json.loads(row[1]); changed['runtime_job_id'] = -1
                sql('UPDATE runtime_jobs SET execution_metadata=? WHERE id=?', (json.dumps(changed), jid))
            if case == 'runtime_input': sql("UPDATE runtime_jobs SET input='{}' WHERE id=?", (jid,))
            if case == 'task_state': sql("UPDATE production_tasks SET status='failed' WHERE id=?", (tid,))
            if case == 'task_payload': sql("UPDATE production_tasks SET branch='changed' WHERE id=?", (tid,))
            if case == 'route': sql("UPDATE production_tasks SET provider='ai_gateway' WHERE id=?", (tid,))
            if case in ('terminal', 'duplicate_result'):
                if case == 'duplicate_result': sql('DROP INDEX IF EXISTS uq_production_results_runtime_job')
                for _ in range(2 if case == 'duplicate_result' else 1):
                    sql("INSERT INTO production_results(runtime_job_id,provider,status) VALUES(?,'github','completed')", (jid,))
            if case == 'duplicate_job':
                sql('DROP INDEX IF EXISTS uq_runtime_jobs_task_id')
                sql("INSERT INTO runtime_jobs(task_id,provider,job_type,status) VALUES(?,'github','github_runtime','created')", (tid,))

        class Provider(base.GitHubProductionProvider):
            calls = 0
            def submit_job(self, job):
                self.calls += 1
                assert committed
                db = sqlite3.connect(base.fixture.DB, timeout=1)
                try:
                    db.execute('BEGIN IMMEDIATE'); db.rollback()
                finally:
                    db.close()
                return super().submit_job(job)

        provider = Provider(client)
        try:
            runtime.execute_authorized_claimed_github_runtime(pid, provider=provider, client=client, before_post=after_commit)
        except ValueError:
            assert case != 'normal'
        else:
            assert case == 'normal', case
        assert committed and provider.calls == client.trigger_count == (1 if case == 'normal' else 0), case
        retained = sql('SELECT execution_state,execution_metadata FROM runtime_jobs WHERE id=?', (jid,))
        if case != 'normal':
            assert retained[0][0] == 'dispatch_intent'
            if case != 'intent_owner': assert retained[0] == committed[0]
        for _ in range(2):
            try:
                runtime.execute_authorized_claimed_github_runtime(pid, provider=provider, client=client)
            except ValueError:
                pass
        assert provider.calls == client.trigger_count == (1 if case == 'normal' else 0)
        assert sql('SELECT execution_state,execution_metadata FROM runtime_jobs WHERE id=?', (jid,)) == retained
        print('G4B_POST_INTENT_' + case.upper() + '=PASS; FAKE_SUBMIT=' + str(provider.calls))
    print('G4B_POST_INTENT_CASES=14')


if __name__ == '__main__':
    def blocked(*args, **kwargs):
        raise AssertionError('REAL_NETWORK_FORBIDDEN')
    try:
        with patch.object(socket.socket, 'connect', blocked), patch.object(socket, 'getaddrinfo', blocked):
            main()
    finally:
        gc.collect()
