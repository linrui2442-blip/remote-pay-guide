from .manager import update_job_status, update_job_result
from .state import JOB_QUEUED, JOB_RUNNING, JOB_COMPLETED, JOB_FAILED
from production.providers import get_provider
from production.results.manager import create_result
from production.tasks.manager import get_task
from production.tasks.scheduler import transition_task


class ProductionRuntimeWorker:
    def _sync_task(self, task_id, status):
        if task_id is None:
            return None
        task = get_task(task_id)
        if task is None or task.status == status:
            return task
        return transition_task(task, status)

    def run(self, job):
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

            result_status = (
                provider_status
                if provider_status in {'submitted', 'running', 'completed', 'failed'}
                else 'failed'
            )
            production_result = create_result({
                'runtime_job_id': job['id'],
                'video_id': str(job.get('task_id')) if job.get('task_id') is not None else None,
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

            if result_status == 'completed':
                update_job_status(job['id'], JOB_COMPLETED)
                self._sync_task(job.get('task_id'), 'completed')
            elif result_status == 'failed':
                update_job_status(job['id'], JOB_FAILED)
                self._sync_task(job.get('task_id'), 'failed')
            else:
                update_job_status(job['id'], JOB_RUNNING)

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
