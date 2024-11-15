import requests
import json
import typing
import time
from bs4 import BeautifulSoup
from collections import defaultdict

inventory_url = "https://nattobot.com/inventory/"

stat_lookup = {
    1: "Attack",
    2: "HP",
    4: "Crit Chance",
    8: "Accuracy",
    16: "Crit Damage",
    32: "Speed",
    64: "Healing Per Round",
    128: "Damage Range",
    256: "x2 Damage Chance",
    512: "Extra Round Chance",
    1024: "Attack",
    2048: "HP",
    4096: "Evasion",
    8192: "Damage Reduction",
    16384: "Defence Penetration",
    32768: "Light Damage",
    65536: "Dark Damage",
    131072: "Fire Damage",
    262144: "Water Damage",
    524288: "Wind Damage",
    1048576: "Lightning Damage",
    2097152: "Earth Damage",
    8388608: "Energy Damage",
}

element_order = ["Light", "Dark", "Fire", "Water", "Wind", "Lightning", "Earth", "Neutral", "Energy"]

flat_stats = {1, 2, 64}

slot_names = {1: "Helmet", 2: "Chest", 3: "Gloves", 4: "Boots", 5: "Necklace", 6: "Bracelet", 7: "Ring", 8: "Earrings"}


def main_stat(stat_index: int, item_level: int, enhancement_level: int) -> float:
    iLN = (15 + item_level * 0.3) + enhancement_level
    exponent = stat_index.bit_length() - 1
    match exponent:
        case 0:
            stat = max(1, iLN * 0.65)
        case 1:
            stat = max(1, iLN * 4)
        case 2:
            stat = iLN * 0.31
        case 3:
            stat = iLN * 0.27
        case 4:
            stat = iLN * 0.34
        case 5:
            stat = iLN * 0.33
        case 6:
            stat = max(1, iLN * 0.31)
        case 7:
            stat = iLN * 0.36
        case 8:
            stat = iLN * 0.19
        case 9:
            stat = iLN * 0.348
        case 10:
            stat = iLN * 0.32
        case 11:
            stat = iLN * 0.36
        case 12:
            stat = iLN * 0.32
        case 13:
            stat = iLN * 0.5
        case 14:
            stat = iLN * 0.29
        case exponent if 15 <= exponent <= 23:
            stat = iLN * 0.37
        case _:
            stat = 1

    return stat


def substat(stat_index: int, stat_level: int, item_level: int, range: float) -> float:
    return main_stat(stat_index, max(30, item_level), 0) * (stat_level * 0.12 + 0.2) * range


def artifact_type(artifact_id: int, slot: int) -> tuple[int, str]:
    set = "Black_Lion" if artifact_id <= 8 else "Holy" if artifact_id <= 16 else "Power"
    return slot, set


def parse_item(
    data: str, ignore_enhancements: bool, enhancement_override: int, substat_levels: list[int] = [1, 1, 1, 1]
) -> dict[str, int | str]:
    assert len(substat_levels) == 4 and all(1 <= level <= 4 for level in substat_levels)
    item_level = data["Level"]
    enhancement_level = data["AdditionalLevel"]
    main = (
        data["MainStatType"],
        main_stat(data["MainStatType"], item_level, enhancement_override if ignore_enhancements else enhancement_level),
    )
    substats = [
        (
            data["SubStats"][i],
            (
                substat(
                    data["SubStats"][i],
                    substat_levels[i] if ignore_enhancements else data["SubStatLevels"][i],
                    item_level,
                    data["SubStatRanges"][i],
                )
                if data["SubStats"][i] > 0
                else 0
            ),
        )
        for i in range(4)
    ]
    slot, set = artifact_type(data["ArtifactID"], data["Slot"])
    return {
        "ID": data["ID"],
        "Slot": slot,
        "Slot_Name": slot_names[slot],
        "Set": set,
        "Main_Stat": main,
        "Substats": substats,
    }


def total_stats(artifacts: list[dict[str, int | str]]) -> tuple[dict[int, float], dict[str, int]]:
    stats = defaultdict(float)
    set_info = {"Black_Lion": 0, "Holy": 0, "Power": 0}
    for artifact in artifacts:
        if artifact is not None:
            set_info[artifact["Set"]] += 1
            stats[artifact["Main_Stat"][0]] += artifact["Main_Stat"][1]
            for stat_type, stat_value in artifact["Substats"]:
                stats[stat_type] += stat_value

    return stats, set_info


def print_stats(stats: dict[int, float], set_info: dict[str, int]) -> None:
    result = []
    for stat_type, stat_value in sorted(stats.items(), key=lambda x: stat_lookup[x[0]]):
        if stat_type > 0:  # substat being zero means not unlocked (lower than level 40 artifact)
            result.append(f"{stat_lookup[stat_type]} +{stat_value:.3f}{'%' if stat_type not in flat_stats else ''}")

    print("\n".join(result))
    print("\nNumber of set artifacts: ", set_info)


def get_inventory_artifacts(
    data: str,
    equipped_only: bool = True,
    ignore_enhancements: bool = False,
    enhancement_override: int = 10,
    substat_levels: dict[int, list[int]] = {},
) -> typing.Optional[list[dict[str, int | str]]]:
    soup = BeautifulSoup(data, "html.parser")
    artifacts = []

    artifacts_div = soup.find(id="artifacts")
    if artifacts_div is None:
        return None
    if equipped_only:
        arts = artifacts_div.find("div", class_="equipment")
    else:
        arts = artifacts_div.find("div", class_="inventory")

    for artifact in arts.find_all("div", attrs={"class": lambda e: e.startswith("item ") if e else False}):
        json_data = artifact.get("data-json", "")
        if json_data:
            data = json.loads(json_data)
            levels = substat_levels.get(data["ID"], data["SubStatLevels"])
            artifacts.append(parse_item(data, ignore_enhancements, enhancement_override, levels))

    return artifacts


def main():
    user_id = input("Input the user's discord id: ")
    res = requests.get(inventory_url + user_id).text
    if "User not found" in res:
        print("User inventory not found")
        print("Window closes in 3 seconds")
        time.sleep(3)
        return
    artifacts = get_inventory_artifacts(res)
    if artifacts is None:
        print("User artifacts are hidden")
        print("Window closes in 3 seconds")
        time.sleep(3)
        return
    print()
    stats, set_info = total_stats(artifacts)
    print_stats(stats, set_info)
    print("\nPress Enter to close the window")
    input()


main()
