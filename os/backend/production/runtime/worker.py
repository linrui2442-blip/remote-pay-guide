from .manager import update_job_status, update_job_result, get_job
from .state import JOB_QUEUED, JOB_RUNNING, JOB_COMPLETED, JOB_FAILED
from production.providers import get_provider
from production.results.manager import create_result, get_result_by_job, update_result
from production.tasks.manager import get_task
from production.tasks.scheduler import transition_task


class ProductionRuntimeWorker:
    ACTIVE_STATUSES = {'submitted', 'running'}
    TERMINAL_STATUSES = {'completed', 'failed'}

    def _sync_task(self, task_id, status):
        if task_id is None:
            return None
        task = get_task(task_id)
        if task is None or task.status == status:
            return task
        return transition_task(task, status)

    def _normalize_status(self, value):
        status = str(value or 'failed').strip().lower()
        if status not in self.ACTIVE_STATUSES | self.TERMINAL_STATUSES:
            return 'failed'
        return status

    def _sync_runtime_status(self, job, status):
        if status == 'completed':
            update_job_status(job['id'], JOB_COMPLETED)
            self._sync_task(job.get('task_id'), 'completed')
        elif status == 'failed':
            update_job_status(job['id'], JOB_FAILED)
            self._sync_task(job.get('task_id'), 'failed')
        else:
            update_job_status(job['id'], JOB_RUNNING)
            task = get_task(job.get('task_id')) if job.get('task_id') is not None else None
            if task and task.status == 'scheduled':
                self._sync_task(job.get('task_id'), 'running')

    def run(self, job):
        # Claimed autonomous AI work must never bypass durable intent/auth.
        import json
        if job.get('provider') == 'ai_gateway' and job.get('id') is not None:
            job = get_job(job['id']) or job
        payload = job.get('input') or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        if job.get('provider') == 'ai_gateway' and (payload.get('parameters') or {}).get('production_routing'):
            raise ValueError('Use the authorized claimed AI runtime entrypoint')
        try:
            update_job_status(job['id'], JOB_QUEUED)
            update_job_status(job['id'], JOB_RUNNING)
            self._sync_task(job.get('task_id'), 'running')

            provider = get_provider(job.get('provider'))
            if provider is None:
                raise Exception('provider not found')

            result = provider.run(job) or {}
            provider_status = result.get('status', 'failed')
            output = result.get('output')
            error = result.get('error')

            update_job_result(job['id'], output, error)

            result_status = self._normalize_status(provider_status)
            # Preserve provider/content identity when the provider returns it;
            # runtime task identity is only a fallback for legacy providers.
            output_identity = output.get('video_id') or output.get('content_id') if isinstance(output, dict) else None
            production_result = create_result({
                'runtime_job_id': job['id'],
                'video_id': output_identity or (str(job.get('task_id')) if job.get('task_id') is not None else None),
                'provider': result.get('provider', job.get('provider')),
                'status': result_status,
                'output': output,
                'error': error if result_status == 'failed' else None,
            })

            if (
                result.get('provider', job.get('provider')) == 'github'
                and result_status == 'submitted'
                and production_result
            ):
                from production.providers.github_completion import complete_github_execution

                production_result = complete_github_execution(
                    production_result['id'],
                    job,
                    client=getattr(provider, 'client', None),
                )
                result_status = production_result.get('status', 'failed')
                output = production_result.get('output')
                error = production_result.get('error')
                result['status'] = result_status
                result['output'] = output
                if error:
                    result['error'] = error
                update_job_result(job['id'], output, error)

            if production_result:
                result_status = production_result.get('status', result_status)
                output = production_result.get('output', output)
                error = production_result.get('error', error)
                result['status'] = result_status
                result['output'] = output
                if error:
                    result['error'] = error

            self._sync_runtime_status(job, result_status)
            result['production_result'] = production_result
            return result

        except Exception as exc:
            error = str(exc)
            update_job_result(job['id'], None, error)
            create_result({
                'runtime_job_id': job['id'],
                'video_id': str(job.get('task_id')) if job.get('task_id') is not None else None,
                'provider': job.get('provider'),
                'status': 'failed',
                'error': error,
            })
            update_job_status(job['id'], JOB_FAILED)
            try:
                self._sync_task(job.get('task_id'), 'failed')
            except Exception:
                pass
            return {
                'status': 'failed',
                'provider': job.get('provider'),
                'error': error,
            }

    def poll(self, job, provider_override=None):
        """Refresh one already-active remote Production job.

        Polling updates the existing ProductionResult in place. It never creates
        a second result for the same Runtime Job and never re-submits the remote
        generation request.
        """
        import json
        if job.get('provider') == 'ai_gateway' and job.get('id') is not None:
            job = get_job(job['id']) or job
        metadata = job.get('execution_metadata') or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if job.get('provider') == 'ai_gateway' and metadata.get('content_plan_id'):
            from production.runtime.orchestrator import refresh_authorized_ai_runtime
            refreshed = refresh_authorized_ai_runtime(metadata['content_plan_id'], provider=provider_override)
            result = refreshed['production_result']
            return {**result, 'production_result': result}
        production_result = get_result_by_job(job['id'])
        if not production_result:
            return {
                'status': 'failed',
                'provider': job.get('provider'),
                'error': 'production result not found for runtime job',
            }

        current_status = self._normalize_status(production_result.get('status'))
        if current_status in self.TERMINAL_STATUSES:
            return {
                'status': current_status,
                'provider': production_result.get('provider') or job.get('provider'),
                'output': production_result.get('output'),
                'error': production_result.get('error'),
                'production_result': production_result,
                'already_terminal': True,
            }

        provider = provider_override or get_provider(job.get('provider'))
        if provider is None:
            raise ValueError('provider not found')
        if not hasattr(provider, 'poll_job'):
            raise ValueError(f"provider {job.get('provider')} does not support polling")

        result = provider.poll_job(job, production_result) or {}
        result_status = self._normalize_status(result.get('status'))
        output = result.get('output')
        if output is None:
            output = production_result.get('output')
        error = result.get('error')

        update_job_result(job['id'], output, None if result_status == 'completed' else error)
        defer_asset = bool((production_result.get("output") or {}).get("defer_asset_binding")
                           or (output or {}).get("defer_asset_binding")
                           or (output or {}).get("g4b_no_asset_binding"))
        production_result = update_result(
            production_result['id'],
            status=result_status,
            output=output,
            error='' if result_status == 'completed' else error,
            bind_asset=not defer_asset,
        )

        result_status = production_result.get('status', result_status)
        output = production_result.get('output', output)
        error = production_result.get('error', error)
        self._sync_runtime_status(job, result_status)

        result['status'] = result_status
        result['provider'] = result.get('provider') or job.get('provider')
        result['output'] = output
        result['error'] = error
        result['production_result'] = production_result
        return result
