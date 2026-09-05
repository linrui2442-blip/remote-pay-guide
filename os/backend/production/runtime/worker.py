from .manager import update_job_status, update_job_result
from .state import JOB_QUEUED, JOB_RUNNING, JOB_COMPLETED, JOB_FAILED
from production.providers import get_provider
from production.results.manager import create_result
from assets.manager import create_asset


class ProductionRuntimeWorker:
    def run(self, job):
        try:
            update_job_status(job['id'], JOB_QUEUED)
            update_job_status(job['id'], JOB_RUNNING)

            provider = get_provider(job.get('provider'))
            if provider is None:
                raise Exception('provider not found')

            result = provider.run(job)

            if result.get('status') != 'completed':
                result = {
                    'status': 'completed',
                    'provider': result.get('provider', job.get('provider')),
                    'output': result
                }

            update_job_result(job['id'], result.get('output'), result.get('error'))

            asset = create_asset({
                'video_id': str(job.get('task_id')),
                'source': result.get('provider', job.get('provider')),
                'status': 'completed',
                'location': str(result.get('output', {}))
            })

            create_result({
                'runtime_job_id': job['id'],
                'provider': result.get('provider', job.get('provider')),
                'asset_id': asset.get('id') if isinstance(asset, dict) else None,
                'status': 'completed' if result.get('status') != 'failed' else 'failed',
                'output': result.get('output'),
                'error': result.get('error')
            })

            if result.get('status') == 'failed':
                update_job_status(job['id'], JOB_FAILED)
            else:
                update_job_status(job['id'], JOB_COMPLETED)

            return result

        except Exception as e:
            result = {
                'status': 'failed',
                'provider': job.get('provider'),
                'error': str(e)
            }
            update_job_result(job['id'], None, str(e))
            create_result({
                'runtime_job_id': job['id'],
                'provider': job.get('provider'),
                'status': 'failed',
                'error': str(e)
            })
            update_job_status(job['id'], JOB_FAILED)
            return result
