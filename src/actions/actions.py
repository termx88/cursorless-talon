import time

from dragonfly import Compound

from ..command import Actions as command_actions
from ..csv_overrides import init_csv_and_watch_changes
from ..cursorless_lists import get_list_ref
from .actions_callback import callback_action_defaults, callback_action_map
from .actions_custom import custom_action_defaults
from .actions_simple import (
    no_wait_actions,
    no_wait_actions_post_sleep,
    positional_action_defaults,
    simple_action_defaults,
)


def get_action_or_ide_command_compound() -> Compound:
    return Compound(
        spec="<simple_action> | <callback_action> | <custom_action>",
        name="action_or_ide_command",
        extras=[
            get_list_ref("simple_action"),
            get_list_ref("callback_action"),
            get_list_ref("custom_action"),
        ],
        value_func=lambda node, extras: cursorless_action_or_ide_command(extras),
    )


def cursorless_action_or_ide_command(m) -> dict:
    try:
        value = m["custom_action"]
        type = "ide_command"
    except KeyError:
        try:
            value = m["simple_action"]
        except KeyError:
            value = m["callback_action"]
        finally:
            type = "cursorless_action"

    return {
        "value": value,
        "type": type,
    }


class Actions:
    def cursorless_command(action_id: str, target: dict):
        """Perform cursorless command on target"""
        if action_id in callback_action_map:
            return callback_action_map[action_id](target)
        elif action_id in no_wait_actions:
            command_actions.cursorless_single_target_command_no_wait(
                action_id, target
            )
            if action_id in no_wait_actions_post_sleep:
                time.sleep(no_wait_actions_post_sleep[action_id])
        else:
            return command_actions.cursorless_single_target_command(
                action_id, target
            )

    def cursorless_ide_command(command_id: str, target: dict):
        """Perform ide command on cursorless target"""
        return ide_command(command_id, target)

    def cursorless_action_or_ide_command(instruction: dict, target: dict):
        """Perform cursorless action or ide command on target (internal use only)"""
        type = instruction["type"]
        value = instruction["value"]
        if type == "cursorless_action":
            return Actions.cursorless_command(value, target)
        elif type == "ide_command":
            return Actions.cursorless_ide_command(value, target)


def ide_command(command_id: str, target: dict, command_options: dict = {}):
    return command_actions.cursorless_single_target_command(
        "executeCommand", target, command_id, command_options
    )


default_values = {
    "simple_action": simple_action_defaults,
    "positional_action": positional_action_defaults,
    "callback_action": callback_action_defaults,
    "custom_action": custom_action_defaults,
    "swap_action": {"swap": "swapTargets"},
    "move_bring_action": {"bring": "replaceWithTarget", "move": "moveToTarget"},
    "wrap_action": {"wrap": "wrapWithPairedDelimiter", "repack": "rewrap"},
    "insert_snippet_action": {"snippet": "insertSnippet"},
    "reformat_action": {"format": "applyFormatter"},
}

ACTION_LIST_NAMES = default_values.keys()


def on_ready():
    init_csv_and_watch_changes("actions", default_values)
    
on_ready()
