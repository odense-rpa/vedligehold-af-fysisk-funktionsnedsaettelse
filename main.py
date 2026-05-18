import asyncio
import logging
import sys

from automation_server_client import (
    AutomationServer,
    Workqueue,
    WorkItemError,
    Credential,
)
from nexus_database_client import NexusDatabaseClient
from kmd_nexus_client import NexusClientManager
from odk_tools.tracking import Tracker
from odk_tools.reporting import report
from kmd_nexus_client.tree_helpers import (
    filter_by_path,
    filter_by_predicate,
)
from datetime import datetime, timedelta

nexus: NexusClientManager
nexus_database_client: NexusDatabaseClient
tracker: Tracker

proces_navn = "Vedligehold af fysisk funktionsnedsættelse"
logger = logging.getLogger(proces_navn)


async def populate_queue(workqueue: Workqueue):
    indsatser = (
        nexus_database_client.hent_fysisk_funktionsnedsættelse_ophørende_indsatser()
    )

    for indsats in indsatser:
        data = {
            "cpr": indsats["business_key"],
            "indsats_id": indsats["id"],
        }

        workqueue.add_item(data=data, reference=f"{indsats['id']}")


async def process_workqueue(workqueue: Workqueue):
    for item in workqueue:
        with item:
            data = item.data

            try:
                borger = nexus.borgere.hent_borger(data["cpr"])
            except Exception:
                # Formentlig invalid cpr - log og skip
                continue

            indsats = hent_indsats(item_data=data)

            if not indsats or not borger:
                # Ingen Fysisk funktionsnedsættelse ophørende indsats at behandle
                return

            vedvarende_indsats = hent_aktiv_vedvarende_indsats(borger)

            try:
                if vedvarende_indsats is None:
                    # Aktiv vedvarende indsats findes ikke - opret ny
                    opret_indsats(borger)

                afslut_tidligere_indsats(indsats)
                tracker.track_task(proces_navn)
            except WorkItemError as e:
                report(
                    report_id="vedligehold_af_fysisk_funktionsnedsaettelse",
                    group="Fejl",
                    json={"Cpr": data["cpr"], "Fejl": str(e)},
                )

                logger.error(f"Error processing item: {data}. Error: {e}")
                item.fail(str(e))


def hent_indsats(item_data: dict) -> dict | None:
    borger = nexus.borgere.hent_borger(item_data["cpr"])

    if not borger:
        return None

    pathway = nexus.borgere.hent_visning(borger=borger)

    if pathway is None:
        raise ValueError(
            f"Kunne ikke finde -Alt for borger {borger['patientIdentifier']['identifier']}"
        )

    indsats_referencer = nexus.borgere.hent_referencer(visning=pathway)

    filtrerede_indsats_referencer = filter_by_path(
        indsats_referencer,
        path_pattern="/*/*/Indsatser/basketGrantReference",
        active_pathways_only=False,
    )

    indsatser = nexus.indsatser.filtrer_indsats_referencer(
        indsats_referencer=filtrerede_indsats_referencer, kun_aktive=True
    )

    indsatser = filter_by_predicate(
        roots=indsatser, predicate=lambda x: x["grantId"] == item_data["indsats_id"]
    )

    if not indsatser:
        return None

    indsats = nexus.indsatser.hent_indsats(indsatser[0])

    return indsats


def hent_aktiv_vedvarende_indsats(borger: dict) -> dict | None:
    pathway = nexus.borgere.hent_visning(borger=borger)

    if pathway is None:
        return None

    indsats_referencer = nexus.borgere.hent_referencer(visning=pathway)

    filtrerede_indsats_referencer = filter_by_path(
        indsats_referencer,
        path_pattern="/ÆHF - Forløbsindplacering (Grundforløb)/Forløbsindplacering/Indsatser/basketGrantReference",
        active_pathways_only=True,
    )

    indsatser = nexus.indsatser.filtrer_indsats_referencer(
        indsats_referencer=filtrerede_indsats_referencer, kun_aktive=True
    )

    indsatser = filter_by_predicate(
        roots=indsatser,
        predicate=lambda x: x["name"] == "Fysisk funktionsnedsættelse vedvarende",
    )

    if not indsatser:
        return None

    indsats = nexus.indsatser.hent_indsats(indsatser[0])

    return indsats


def opret_indsats(borger: dict):
    i_dag = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        nexus.indsatser.opret_indsats(
            borger=borger,
            grundforløb="ÆHF - Forløbsindplacering (Grundforløb)",
            forløb="Forløbsindplacering",
            indsats="Fysisk funktionsnedsættelse vedvarende",
            oprettelsesform="Ansøg, Bevilg, Bestil",
            felter={
                "workflowRequestedDate": i_dag,
                "workflowApprovedDate": i_dag,
                "orderedDate": i_dag,
                "entryDate": i_dag,
                "billingStartDate": i_dag,
            },
        )
    except Exception:
        raise WorkItemError("Kunne ikke oprette ny indsats")


def afslut_tidligere_indsats(indsats: dict):
    i_går = datetime.today().replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)

    try:
        nexus.indsatser.rediger_indsats(
            indsats,
            {
                "billingEndDate": i_går,
                "basketGrantEndDate": i_går,
            },
            "Afslut",
        )
    except Exception:
        raise WorkItemError("Kunne ikke afslutte tidligere indsats")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    nexus_credential = Credential.get_credential("KMD Nexus - produktion")
    nexus_database_credential = Credential.get_credential("KMD Nexus - database")
    tracking_credential = Credential.get_credential("Odense SQL Server")

    nexus = NexusClientManager(
        client_id=nexus_credential.username,
        client_secret=nexus_credential.password,
        instance=nexus_credential.data["instance"],
    )

    nexus_database_client = NexusDatabaseClient(
        host=nexus_database_credential.data["hostname"],
        port=nexus_database_credential.data["port"],
        user=nexus_database_credential.username,
        password=nexus_database_credential.password,
        database=nexus_database_credential.data["database_name"],
    )

    tracker = Tracker(
        username=tracking_credential.username, password=tracking_credential.password
    )

    logger = logging.getLogger(__name__)

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue("new")
        asyncio.run(populate_queue(workqueue))
        exit(0)

    # Process workqueue
    asyncio.run(process_workqueue(workqueue))
