from .manager import create_job, get_job, get_jobs, update_job_result, update_job_status

__all__ = [
    "create_job",
    "get_job",
    "get_jobs",
    "update_job_result",
    "update_job_status",
    "ProductionRuntimeWorker",
]


def __getattr__(name):
    """Load the runtime worker lazily to avoid scheduler/worker import cycles."""
    if name == "ProductionRuntimeWorker":
        from .worker import ProductionRuntimeWorker

        return ProductionRuntimeWorker
    raise AttributeError(name)
