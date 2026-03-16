import typer
import shutil
import subprocess
from typing import Annotated, Optional
from frappe_manager import CLI_BENCHES_DIRECTORY
from frappe_manager.site_manager.SiteManager import BenchesManager
from frappe_manager.site_manager.site import Bench
from frappe_manager.site_manager.site_exceptions import BenchSSLCertificateNotIssued
from frappe_manager.services_manager.services import ServicesManager
from frappe_manager.ssl_manager.certificate_exceptions import SSLCertificateNotDueForRenewalError
from frappe_manager.utils.callbacks import sitename_callback, sites_autocompletion_callback
from frappe_manager.display_manager.DisplayManager import richprint

ssl_root_command = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")
SSL_RENEW_CRON_MARKER = "# fm-ssl-auto-renew"
SSL_RENEW_CRON_SCHEDULE = "0 3 * * *"


def _get_services_manager(ctx: typer.Context) -> ServicesManager:
    """Ensure services manager is available for standalone subcommand execution."""
    ctx.ensure_object(dict)

    services_manager = ctx.obj.get("services")
    if services_manager:
        return services_manager

    services_manager = ServicesManager(verbose=bool(ctx.obj.get("verbose", False)))
    services_manager.set_typer_context(ctx)
    services_manager.init()
    services_manager.entrypoint_checks(start=True)

    ctx.obj["services"] = services_manager
    return services_manager


@ssl_root_command.command()
def delete(
    ctx: typer.Context,
    benchname: Annotated[
        Optional[str],
        typer.Argument(
            help="Name of the bench.", autocompletion=sites_autocompletion_callback, callback=sitename_callback
        ),
    ] = None,
):
    """Delete bench ssl certficate."""

    if not benchname:
        raise typer.BadParameter("Please provide benchname.", param_hint="benchname")

    services_manager = _get_services_manager(ctx)
    bench = Bench.get_object(benchname, services_manager)
    richprint.change_head("Removing SSL certificate")

    if not bench.has_certificate():
        richprint.exit(f"{benchname} doesn't have SSL certificate issued.")
    bench.remove_certificate()
    richprint.print("Removed SSL certificate.")


@ssl_root_command.command()
def renew(
    ctx: typer.Context,
    benchname: Annotated[
        Optional[str],
        typer.Argument(help="Name of the bench.", autocompletion=sites_autocompletion_callback),
    ] = None,
    all: Annotated[bool, typer.Option(help="Renew ssl cert for all benches.")] = False,
):
    """Renew bench ssl certficate."""

    if not all and not benchname:
        raise typer.BadParameter("Please provide benchname or use --all.", param_hint="benchname")

    services_manager = _get_services_manager(ctx)
    benches = BenchesManager(CLI_BENCHES_DIRECTORY, services=services_manager)

    if all:
        sites_list = list(benches.get_all_bench().keys())
    else:
        assert benchname is not None
        sites_list = [benchname]

    for benchname in sites_list:
        bench = Bench.get_object(benchname, services_manager)
        richprint.change_head("Renew certificate")
        try:
            bench.renew_certificate()
        except (BenchSSLCertificateNotIssued, SSLCertificateNotDueForRenewalError) as e:
            richprint.warning(e.message)

        except Exception as e:
            richprint.warning(str(e))


@ssl_root_command.command("create-cron")
def create_cron():
    """Create a cron entry to auto-renew SSL certificates if one does not already exist."""

    fm_executable = shutil.which("fm")
    if not fm_executable:
        richprint.exit("Unable to find fm executable in PATH.")

    list_cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if list_cron.returncode == 0:
        cron_lines = list_cron.stdout.splitlines()
    else:
        error_output = f"{list_cron.stderr}\n{list_cron.stdout}".lower()
        if "no crontab for" in error_output:
            cron_lines = []
        else:
            richprint.exit("Unable to read current crontab.", error_msg=list_cron.stderr.strip())

    already_exists = any(
        SSL_RENEW_CRON_MARKER in line or ("fm" in line and "ssl renew --all" in line) for line in cron_lines
    )
    if already_exists:
        richprint.print("SSL renew cron already exists. Skipping.")
        return

    cron_command = f"{fm_executable} ssl renew --all >/dev/null 2>&1 {SSL_RENEW_CRON_MARKER}"
    cron_lines.append(f"{SSL_RENEW_CRON_SCHEDULE} {cron_command}")
    new_crontab = "\n".join(cron_lines).strip() + "\n"

    install_cron = subprocess.run(["crontab", "-"], input=new_crontab, capture_output=True, text=True)
    if install_cron.returncode != 0:
        richprint.exit("Unable to create SSL renew cron.", error_msg=install_cron.stderr.strip())

    richprint.print(f"Created SSL renew cron: {SSL_RENEW_CRON_SCHEDULE} {fm_executable} ssl renew --all")
