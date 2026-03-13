import argparse
import sys
from libs.core.config import get_settings
from libs.db.session import get_session_factory
from libs.subgraph.sync import resolve_subgraph_url, sync_vaults, sync_vault_events

def run(verbose: bool = False) -> None:
    settings = get_settings()
    url = resolve_subgraph_url(settings)
    if not url:
        print("Subgraph URL not set.", file=sys.stderr)
        sys.exit(1)

    session_factory = get_session_factory()
    chain_id = settings.chain_base_sepolia_id
    batch = settings.indexer_batch_size
    api_key = None if "gateway.thegraph.com" in url else settings.subgraph_api_key

    with session_factory() as db:
        v = sync_vaults(url, db, chain_id=chain_id, batch=batch, api_key=api_key)
        ev = sync_vault_events(url, db, chain_id=chain_id, batch=batch, api_key=api_key)
        print(f"Synced {v} vaults, {ev} vault_events from subgraph (chain_id={chain_id})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true", help="Print received/inserted counts")
    parser.add_argument("--loop", action="store_true", help="DEPRECATED: Use docker-compose services (beat/worker) instead")
    args = parser.parse_args()
    if args.loop:
        print("Warning: --loop is deprecated. Please run via 'make beat' or 'make db-up'.")
    run(verbose=args.verbose)
