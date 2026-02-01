import copy
import json
from typing import List, Optional

import flux
import flux.job
from rich import print

# TODO: need to use full path for sqlalchemy
# need to also set pwd to be where job is submit, otherwise we get where server running
# finish writing up demo


def get_handle(uri: Optional[str] = None) -> flux.Flux:
    """Helper to get a Flux handle, optionally connecting to a remote URI."""
    if uri:
        return flux.Flux(uri)
    return flux.Flux()


def flux_submit_batch(
    commands: List[List[str]],
    uri: Optional[str] = None,
    modules: List[str] = None,
    prologs: List[str] = None,
    epilogs: List[str] = None,
    services: List[str] = None,
    job_name: str = None,
    logs_dir: str = None,
    cwd: str = None,
    nodes: int = 1,
    nslots: int = 1,
    environment: List[str] = None,
    time_limit: str = None,
    debug: bool = False,
):
    """
    Submits a batch job to Flux using flux-batch

    This is more experimental, so I am adding here and not to flux-mcp.
    """
    # Defaults of listy things
    services = services or []
    epilogs = epilogs or []
    prologs = prologs or []
    modules = modules or []

    # Assume this is an error.
    if not commands:
        return json.dumps({"success": False, "error": "No commands provided"})

    try:
        import flux_batch

        handle = get_handle(uri)

        # Create your batch job with some number of commands
        jobs = flux_batch.BatchJobV1()
        for command in commands:
            jobs.add_job(command)

        # Wrap it up into a jobspec
        spec = flux_batch.BatchJobspecV1.from_jobs(
            jobs,
            nodes=nodes,
            nslots=nslots,
            cwd=cwd,
            time_limit=time_limit,
            job_name=job_name,
            env=environment,
            logs_dir=logs_dir,
        )

        # Add prolog, epilogs, modules, and services
        # It's at the user discretion to not provide the same named services as modules. YOLO.
        for prolog in prologs:
            spec.add_prolog(prolog)
        for epilog in epilogs:
            spec.add_epilog(epilog)
        for module in modules:
            spec.add_module(module)

        # Preview it, if asked for debug
        if debug:
            print(flux_batch.submit(handle, spec, dry_run=True))
            jobspec = flux_batch.jobspec(spec)
            show_jobspec(jobspec)

        # Submit that bad boi. If this is running on the login/head node, we submit there
        # note that modules and services will be run under the job, as they should be.
        jobid = flux_batch.submit(handle, spec)

        # Return success with the integer ID
        return json.dumps({"success": True, "job_id": int(jobid), "uri": uri or "local"})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def show_jobspec(jobspec):
    # Cleaned up jobspec to print (only show flux settings)
    environ = copy.deepcopy(jobspec["attributes"]["system"]["environment"])
    updates = {}
    for key, value in environ.items():
        if key.startswith("FLUX_"):
            updates[key] = value
    jobspec["attributes"]["system"]["environment"] = updates
    print(jobspec)
