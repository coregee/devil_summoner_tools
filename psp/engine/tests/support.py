"""Shared private-ISO fixtures for dependent engine surfaces."""

from functools import lru_cache

from psp.engine import build


@lru_cache(maxsize=1)
def name_ready_boot() -> bytes:
    stock, _, _ = build._source_entries()
    title = build.build_title_help_ui(stock, build._metric_widths())
    config = build.build_config_menu(stock, title.data, build._config_font_contract())
    command = build.build_command_menu_help(stock, config.data)
    event = build.build_event_window(stock, command.data, build.load_eve_widths())
    return build.build_name_entry(stock, event.data).data


@lru_cache(maxsize=1)
def map_ready_boot() -> bytes:
    stock, _, _ = build._source_entries()
    savedata = build.build_savedata(stock, name_ready_boot())
    dungeon = build.build_dungeon_locations(stock, savedata.data, build._dungeon_location_font_contract())
    compendium = build.build_compendium(stock, dungeon.data, build.load_eve_widths())
    items = build.build_item_runtime(stock, compendium.data, build._source_regdata(), build.load_eve_widths())
    return build.build_map2d(stock, items.data, build._map2d_font_contract()).data
