import csv
import os
from collections.abc import Container
from datetime import datetime
from pathlib import Path
from typing import Optional

from .cursorless_lists import append_list

# from .conventions import get_cursorless_list_name
from .vendor.inflection import pluralize

SPOKEN_FORM_HEADER = "Spoken form"
CURSORLESS_IDENTIFIER_HEADER = "Cursorless identifier"


def init_csv_and_watch_changes(
    filename: str,
    default_values: dict[str, dict[str, str]],
    extra_ignored_values: Optional[list[str]] = None,
    allow_unknown_values: bool = False,
    default_list_name: Optional[str] = None,
    headers: list[str] = [SPOKEN_FORM_HEADER, CURSORLESS_IDENTIFIER_HEADER],
    no_update_file: bool = False,
    pluralize_lists: Optional[list[str]] = [],
):
    """
    Initialize a cursorless settings csv, creating it if necessary, and watch
    for changes to the csv.  Talon lists will be generated based on the keys of
    `default_values`.  For example, if there is a key `foo`, there will be a
    list created called `user.cursorless_foo` that will contain entries from
    the original dict at the key `foo`, updated according to customization in
    the csv at

        actions.path.talon_user() / "cursorless-settings" / filename

    Note that the settings directory location can be customized using the
    `user.cursorless_settings_directory` setting.

    Args:
        filename (str): The name of the csv file to be placed in
        `cursorles-settings` dir
        default_values (dict[str, dict]): The default values for the lists to
        be customized in the given csv
        extra_ignored_values list[str]: Don't throw an exception if any of
        these appear as values; just ignore them and don't add them to any list
        allow_unknown_values bool: If unknown values appear, just put them in the list
        default_list_name Optional[str]: If unknown values are allowed, put any
        unknown values in this list
        no_update_file Optional[bool]: Set this to `TRUE` to indicate that we should
        not update the csv. This is used generally in case there was an issue coming up with the default set of values so we don't want to persist those to disk
        pluralize_lists: Create plural version of given lists
    """
    if extra_ignored_values is None:
        extra_ignored_values = []

    file_path = get_full_path(filename)
    super_default_values = get_super_values(default_values)

    file_path.parent.mkdir(parents=True, exist_ok=True)

    # def on_watch(path, flags):
    #     if file_path.match(path):
    #         current_values, has_errors = read_file(
    #             file_path,
    #             headers,
    #             super_default_values.values(),
    #             extra_ignored_values,
    #             allow_unknown_values,
    #         )
    #         update_dicts(
    #             default_values,
    #             current_values,
    #             extra_ignored_values,
    #             allow_unknown_values,
    #             default_list_name,
    # 		      pluralize_lists,
    #         )

    # fs.watch(str(file_path.parent), on_watch)

    if file_path.is_file():
        current_values = update_file(
            file_path,
            headers,
            super_default_values,
            extra_ignored_values,
            allow_unknown_values,
            no_update_file,
        )
        update_dicts(
            default_values,
            current_values,
            extra_ignored_values,
            allow_unknown_values,
            default_list_name,
            pluralize_lists,
        )
    else:
        if not no_update_file:
            create_file(file_path, headers, super_default_values)
        update_dicts(
            default_values,
            super_default_values,
            extra_ignored_values,
            allow_unknown_values,
            default_list_name,
            pluralize_lists,
        )

    # def unsubscribe():
    #     fs.unwatch(str(file_path.parent), on_watch)

    # return unsubscribe


def is_removed(value: str):
    return value.startswith("-")


def update_dicts(
    default_values: dict[str, dict],
    current_values: dict,
    extra_ignored_values: list[str],
    allow_unknown_values: bool,
    default_list_name: Optional[str],
    pluralize_lists: Optional[list[str]],
):
    # Create map with all default values
    results_map = {}
    for list_name, dict in default_values.items():
        for key, value in dict.items():
            results_map[value] = {"key": key, "value": value, "list": list_name}

    # Update result with current values
    for key, value in current_values.items():
        try:
            results_map[value]["key"] = key
        except KeyError:
            if value in extra_ignored_values:
                pass
            elif allow_unknown_values:
                results_map[value] = {
                    "key": key,
                    "value": value,
                    "list": default_list_name,
                }
            else:
                raise

    # Convert result map back to result list
    results = {res["list"]: {} for res in results_map.values()}
    for obj in results_map.values():
        value = obj["value"]
        key = obj["key"]
        if not is_removed(key):
            for k in key.split("|"):
                results[obj["list"]][k.strip()] = value

    # Assign result to talon context list
    for list_name, dict in results.items():
        append_list(list_name, dict)
        if list_name in pluralize_lists:
            list_plural_name = f"{list_name}_plural"
            append_list(list_plural_name, {pluralize(k): v for k, v in dict.items()})


def update_file(
    path: Path,
    headers: list[str],
    default_values: dict[str, str],
    extra_ignored_values: list[str],
    allow_unknown_values: bool,
    no_update_file: bool,
):
    current_values, has_errors = read_file(
        path,
        headers,
        default_values.values(),
        extra_ignored_values,
        allow_unknown_values,
    )
    current_identifiers = current_values.values()

    missing = {}
    for key, value in default_values.items():
        if value not in current_identifiers:
            missing[key] = value

    if missing:
        if has_errors or no_update_file:
            print(
                "NOTICE: New cursorless features detected, but refusing to update "
                "csv due to errors.  Please fix csv errors above and restart talon"
            )
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            lines = [
                f"# {timestamp} - New entries automatically added by cursorless",
                *[create_line(key, missing[key]) for key in sorted(missing)],
            ]
            with open(path, "a") as f:
                f.write("\n\n" + "\n".join(lines))

            print(f"New cursorless features added to {path.name}")
            for key in sorted(missing):
                print(f"{key}: {missing[key]}")
            print(
                "See release notes for more info: "
                "https://github.com/cursorless-dev/cursorless/blob/main/CHANGELOG.md"
            )

    return current_values


def create_line(*cells: str):
    return ", ".join(cells)


def create_file(path: Path, headers: list[str], default_values: dict):
    lines = [create_line(key, default_values[key]) for key in sorted(default_values)]
    lines.insert(0, create_line(*headers))
    lines.append("")
    path.write_text("\n".join(lines))


def csv_error(path: Path, index: int, message: str, value: str):
    """Check that an expected condition is true

    Note that we try to continue reading in this case so cursorless doesn't get bricked

    Args:
        path (Path): The path of the CSV (for error reporting)
        index (int): The index into the file (for error reporting)
        text (str): The text of the error message to report if condition is false
    """
    print(f"ERROR: {path}:{index+1}: {message} '{value}'")


def read_file(
    path: Path,
    headers: list[str],
    default_identifiers: Container[str],
    extra_ignored_values: list[str],
    allow_unknown_values: bool,
):
    with open(path) as csv_file:
        # Use `skipinitialspace` to allow spaces before quote. `, "a,b"`
        csv_reader = csv.reader(csv_file, skipinitialspace=True)
        rows = list(csv_reader)

    result = {}
    used_identifiers = []
    has_errors = False
    seen_headers = False

    for i, row in enumerate(rows):
        # Remove trailing whitespaces for each cell
        row = [x.rstrip() for x in row]
        # Exclude empty or comment rows
        if len(row) == 0 or (len(row) == 1 and row[0] == "") or row[0].startswith("#"):
            continue

        if not seen_headers:
            seen_headers = True
            if row != headers:
                has_errors = True
                csv_error(path, i, "Malformed header", create_line(*row))
                print(f"Expected '{create_line(*headers)}'")
            continue

        if len(row) != len(headers):
            has_errors = True
            csv_error(
                path,
                i,
                f"Malformed csv entry. Expected {len(headers)} columns.",
                create_line(*row),
            )
            continue

        key, value = row

        if (
            value not in default_identifiers
            and value not in extra_ignored_values
            and not allow_unknown_values
        ):
            has_errors = True
            csv_error(path, i, "Unknown identifier", value)
            continue

        if value in used_identifiers:
            has_errors = True
            csv_error(path, i, "Duplicate identifier", value)
            continue

        result[key] = value
        used_identifiers.append(value)

    return result, has_errors


def get_full_path(filename: str):
    if not filename.endswith(".csv"):
        filename = f"{filename}.csv"

    # using cursorless/settings folder for settings
    settings_directory = Path(os.path.join(os.path.dirname(__file__), "settings"))
    # user_dir: Path = settings.SETTINGS["paths"]["BASE_PATH"]

    return (settings_directory / filename).resolve()


def get_super_values(values: dict[str, dict[str, str]]):
    result: dict[str, str] = {}
    for value_dict in values.values():
        result.update(value_dict)
    return result
