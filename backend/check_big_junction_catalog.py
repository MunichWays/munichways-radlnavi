"""Validate the runtime catalog offline before deployment."""

from src.big_junctions import approved_movements, catalog


if __name__ == "__main__":
    value = catalog()
    movements = approved_movements()
    print(f"Catalog {value['version']}: {len({m['junctionId'] for m in movements})} active junctions, "
          f"{len(movements)} reviewed movements, {len(value.get('excluded', []))} explicit exclusions.")
