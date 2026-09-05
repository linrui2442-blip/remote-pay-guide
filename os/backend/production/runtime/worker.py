from .manager import update_job_status, update_job_result
from .state import JOB_QUEUED, JOB_RUNNING, JOB_COMPLETED, JOB_FAILED
from production.providers import get_provider

class ProductionRuntimeWorker:
    def run(self, job):
        try:
            update_job_status(job['id'], JOB_QUEUED)
            update_job_status(job['id'], JOB_RUNNING)
            provider = get_provider(job['provider'])
            if provider is None:
                raise Exception('provider not found')
            result = provider.run(job)
            update_job_result(job['id'], str(result), None)
            update_job_status(job['id'], JOB_COMPLETED)
            return result
        except Exception as e:
            update_job_result(job['id'], None, str(e))
            update_job_status(job['id'], JOB_FAILED)
            return {'status':'failed','error':str(e)}
