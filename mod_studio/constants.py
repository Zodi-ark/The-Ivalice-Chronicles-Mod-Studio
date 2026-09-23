"""
Ground-truth constants for the FFT: Ivalice Chronicles Job Data table.

All flag names below are copied from the mod loader's own source so the
XML this tool writes will always use names the loader actually recognizes:
https://github.com/Nenkai/fftivc.utility.modloader/blob/master/fftivc.utility.modloader.Interfaces/Tables/Structures/JOB_DATA.cs
"""

# ---------------------------------------------------------------------------
# Reference locations
# ---------------------------------------------------------------------------

MODLOADER_OWNER = "Nenkai"
MODLOADER_REPO = "fftivc.utility.modloader"
MODLOADER_BRANCH = "master"
# Reference tables shipped inside the mod loader repo, under this shared path.
TABLEDATA_REPO_DIR = "fftivc.utility.modloader/TableData"
TABLE_FILENAMES = {
    "job": "JobData.xml",
    "job_command": "JobCommandData.xml",
    "ability": "AbilityData.xml",
    "item": "ItemData.xml",
    "item_weapon": "ItemWeaponData.xml",
    "item_armor": "ItemArmorData.xml",
    "item_shield": "ItemShieldData.xml",
    "item_accessory": "ItemAccessoryData.xml",
    "item_equip_bonus": "ItemEquipBonusData.xml",
    "item_options": "ItemOptionsData.xml",
    "item_shops": "ItemShopsData.xml",
    "map_trap": "MapTrapFormationData.xml",
    "ability_effect": "AbilityEffectNumberFilterData.xml",
    "ability_animation": "AbilityTypeData.xml",
}


def table_raw_url(filename: str) -> str:
    return (
        f"https://raw.githubusercontent.com/{MODLOADER_OWNER}/{MODLOADER_REPO}/"
        f"{MODLOADER_BRANCH}/{TABLEDATA_REPO_DIR}/{filename}"
    )

FF16TOOLS_OWNER = "Nenkai"
FF16TOOLS_REPO = "FF16Tools"
FF16TOOLS_LATEST_RELEASE_API = (
    f"https://api.github.com/repos/{FF16TOOLS_OWNER}/{FF16TOOLS_REPO}/releases/latest"
)

# AudioMog (github.com/Yoraiz0r/AudioMog, MIT) - unpacks/repacks .sab sound
# archives for the Sounds tab. Ships as a single .exe (not zipped), unlike
# FF16Tools.CLI - see audiomog.py.
AUDIOMOG_OWNER = "Yoraiz0r"
AUDIOMOG_REPO = "AudioMog"
AUDIOMOG_LATEST_RELEASE_API = (
    f"https://api.github.com/repos/{AUDIOMOG_OWNER}/{AUDIOMOG_REPO}/releases/latest"
)

MAX_JOB_ID = 175          # hardcoded table size is 176 (0-175)
TOTAL_JOB_SLOTS = 176

GAME_MODES = ["enhanced", "classic", "combined"]
SUPPORTED_APP_IDS = {
    "enhanced": ["fft_enhanced.exe"],
    "classic": ["fft_classic.exe"],
    "combined": ["fft_enhanced.exe", "fft_classic.exe"],
}

# ---------------------------------------------------------------------------
# Equippable items - 34 valid flags (from JobEquippableItems1-5Flags)
# Grouped the way a person shopping for gear would think about it.
# ---------------------------------------------------------------------------

EQUIP_GROUPS = {
    "Weapons - Blades": ["Knife", "NinjaBlade", "Sword", "KnightSword", "Katana", "FellSword"],
    "Weapons - Blunt/Heavy": ["Axe", "Flail", "Polearm", "Pole"],
    "Weapons - Ranged": ["Gun", "Crossbow", "Bow"],
    "Weapons - Caster": ["Rod", "Staff", "Book", "Instrument"],
    "Unarmed": ["Unarmed"],
    "Shields & Headgear": ["Shield", "Helmet", "Hat", "HairAdornment"],
    "Body Armor": ["Armor", "Clothing", "Robe", "Cloth"],
    "Accessories": ["Ring", "Armlet", "Armguard", "Cloak", "Perfume", "Shoes", "Bag", "LipRouge"],
}

# Flat list in a stable order, used for anything that needs "all 34 items".
EQUIP_ITEMS = [item for group in EQUIP_GROUPS.values() for item in group]

# ---------------------------------------------------------------------------
# Status effects - 40 flags total (5 sets of 8, from JobInnateStartImmuneStatus)
# "Unused1"/"Unused2" are real bits that appear in vanilla data (e.g. job 18,
# job 28), so they're kept for fidelity even though they have no known effect.
# ---------------------------------------------------------------------------

STATUS_GROUPS = {
    "Set 1": ["Unused1", "Crystal", "KO", "Undead", "Charging", "Jump", "Defending", "Performing"],
    "Set 2": ["Stone", "Traitor", "Blind", "Confuse", "Silence", "Vampire", "Unused2", "Chest"],
    "Set 3": ["Oil", "Float", "Reraise", "Invisible", "Berserk", "Chicken", "Toad", "Critical"],
    "Set 4": ["Poison", "Regen", "Protect", "Shell", "Haste", "Slow", "Stop", "Wall"],
    "Set 5": ["Faith", "Atheist", "Charm", "Sleep", "Immobilize", "Disable", "Reflect", "Doom"],
}
STATUS_FLAGS = [s for group in STATUS_GROUPS.values() for s in group]

# ---------------------------------------------------------------------------
# Elements - 8 flags (from JobElementFlags), same 8 values used for
# AbsorbElements / NullifyElements / HalveElements / WeakElements.
# ---------------------------------------------------------------------------

ELEMENT_FLAGS = ["Fire", "Lightning", "Ice", "Wind", "Earth", "Water", "Holy", "Dark"]

# ---------------------------------------------------------------------------
# Field metadata: every editable Job property, its kind, and valid range.
# kind is one of: "int", "flags"
# ---------------------------------------------------------------------------

NUMERIC_FIELDS = {
    # name: (min, max, label, help text)
    "HPGrowth": (0, 255, "HP Growth", "Lower = faster HP growth per level."),
    "HPMultiplier": (0, 255, "HP Multiplier", ""),
    "MPGrowth": (0, 255, "MP Growth", "Lower = faster MP growth per level."),
    "MPMultiplier": (0, 255, "MP Multiplier", ""),
    "SpeedGrowth": (0, 255, "Speed Growth", ""),
    "SpeedMultiplier": (0, 255, "Speed Multiplier", ""),
    "PAGrowth": (0, 255, "Physical Attack Growth", ""),
    "PAMultiplier": (0, 255, "Physical Attack Multiplier", ""),
    "MAGrowth": (0, 255, "Magic Attack Growth", ""),
    "MAMultiplier": (0, 255, "Magic Attack Multiplier", ""),
    "Move": (0, 255, "Move", ""),
    "Jump": (0, 255, "Jump", "131/132 are special (innate Fly/Float-tier jump)."),
    "CharacterEvasion": (0, 255, "Evasion", ""),
    "MonsterPortrait": (0, 255, "Monster Portrait ID", "Only relevant for monster jobs."),
    "MonsterPalette": (0, 255, "Monster Palette ID", "Only relevant for monster jobs."),
    "MonsterGraphic": (0, 255, "Monster Graphic ID", "Only relevant for monster jobs."),
}

FLAG_FIELDS = {
    # name: (choices, label)
    "EquippableItems": (EQUIP_ITEMS, "Equippable Items"),
    "InnateStatus": (STATUS_FLAGS, "Innate Status"),
    "ImmuneStatus": (STATUS_FLAGS, "Immune Status"),
    "StartingStatus": (STATUS_FLAGS, "Starting Status"),
    "AbsorbElements": (ELEMENT_FLAGS, "Absorbs"),
    "NullifyElements": (ELEMENT_FLAGS, "Nullifies"),
    "HalveElements": (ELEMENT_FLAGS, "Halves Damage From"),
    "WeakElements": (ELEMENT_FLAGS, "Weak To"),
}

# ---------------------------------------------------------------------------
# Innate abilities - shown as a name dropdown, not a raw ID field.
#
# Per FFTPatcher (github.com/Glain/FFTPatcher), only abilities 0x1C6-0x1E5
# (hex) function correctly as Innate Abilities - that's decimal 454-485,
# the same 32 "Support Abilities" a human job could equip from the job
# menu. Names below are from FFTPatcher's own PSP ability list
# (PatcherLib.Resources/Resources/PSP/Abilities/Abilities.xml), which
# already uses decimal IDs matching the mod loader's convention.
#
# The vanilla JobData.xml also uses these same fields on MONSTER jobs to
# hold movement/monster-only traits (Fly, Swim, Counter, Teleport, etc.) -
# those aren't "Support Abilities" in the human sense, but they're real
# data already present in the game, so they're included too rather than
# risking the dropdown silently misrepresenting or discarding them.
# ---------------------------------------------------------------------------

ABILITY_FIELD_NAMES = ["InnateAbilityId1", "InnateAbilityId2", "InnateAbilityId3", "InnateAbilityId4"]
ABILITY_FIELD_LABELS = {
    "InnateAbilityId1": "Innate Ability 1",
    "InnateAbilityId2": "Innate Ability 2",
    "InnateAbilityId3": "Innate Ability 3",
    "InnateAbilityId4": "Innate Ability 4",
}

SUPPORT_ABILITIES = [
    (454, "Equip Heavy Armor"),
    (455, "Equip Shields"),
    (456, "Equip Swords"),
    (457, "Equip Katana"),
    (458, "Equip Crossbows"),
    (459, "Equip Polearms"),
    (460, "Equip Axes"),
    (461, "Equip Guns"),
    (462, "Halve MP"),
    (463, "JP Boost"),
    (464, "EXP Boost"),
    (465, "Attack Boost"),
    (466, "Defense Boost"),
    (467, "Arcane Strength"),
    (468, "Arcane Defense"),
    (469, "Concentration"),
    (470, "Tame"),
    (471, "Poach"),
    (472, "Brawler"),
    (473, "Beast Tongue"),
    (474, "Throw Items"),
    (475, "Safeguard"),
    (476, "Doublehand"),
    (477, "Dual Wield"),
    (478, "Beastmaster"),
    (479, "Defend"),
    (480, "Reequip"),
    (481, "(Unknown Ability 481)"),
    (482, "Swiftness"),
    (483, "CT 0"),
    (484, "HP Boost"),
    (485, "Vehemence"),
]

OTHER_INNATE_ABILITIES = [  # movement/monster traits observed in vanilla monster job data
    (430, "Faith Boost"),
    (442, "Counter"),
    (492, "Ignore Elevation"),
    (497, "(Cannot enter water)"),
    (498, "Teleport"),
    (499, "Master Teleportation"),
    (500, "Ignore Weather"),
    (501, "Ignore Terrain"),
    (502, "Waterwalking"),
    (503, "Swim"),
    (505, "Waterbreathing"),
    (506, "Levitate"),
    (507, "Fly"),
]

INNATE_ABILITY_CHOICES = [(0, "(None)")] + SUPPORT_ABILITIES + OTHER_INNATE_ABILITIES
INNATE_ABILITY_NAME_BY_ID = dict(INNATE_ABILITY_CHOICES)

# ---------------------------------------------------------------------------
# Job Command (skillset) editing - AbilityId1-16 (a command's action menu)
# should only offer action-type abilities, while ReactionSupportMovementId1-6
# should only offer Reaction/Support/Movement-type ones. AbilityData.xml's
# own <AbilityType> field is the authoritative source for this split (a
# fixed id range was tried first and turned out to have gaps - 422-429 are
# Reaction too, not just 430+) - see xml_io.load_ability_types(). These are
# the AbilityType values that fall in each bucket; "None" (ids 0, 510, 511 -
# empty/unused slots) belongs in neither.
# ---------------------------------------------------------------------------

ACTION_ABILITY_TYPES = {"Normal", "Item", "Throwing", "Jumping", "Aim", "Math"}
RSM_ABILITY_TYPES = {"Reaction", "Support", "Movement"}

MAX_ABILITY_ID = 511  # hardcoded AbilityData table size is 512 (0-511)

# JobCommandId gets its own dedicated dropdown widget (choices come from the
# live-fetched JobCommandData.xml, not a fixed constant), so it's tracked as
# its own category rather than living in NUMERIC_FIELDS or ABILITY_FIELD_NAMES.
JOB_COMMAND_FIELD_NAME = "JobCommandId"

# Order fields should be written in the output XML (matches the reference file).
FIELD_ORDER = [
    "JobCommandId",
    "InnateAbilityId1", "InnateAbilityId2", "InnateAbilityId3", "InnateAbilityId4",
    "EquippableItems",
    "HPGrowth", "HPMultiplier",
    "MPGrowth", "MPMultiplier",
    "SpeedGrowth", "SpeedMultiplier",
    "PAGrowth", "PAMultiplier",
    "MAGrowth", "MAMultiplier",
    "Move", "Jump", "CharacterEvasion",
    "InnateStatus", "ImmuneStatus", "StartingStatus",
    "AbsorbElements", "NullifyElements", "HalveElements", "WeakElements",
    "MonsterPortrait", "MonsterPalette", "MonsterGraphic",
]

assert set(FIELD_ORDER) == (
    set(NUMERIC_FIELDS) | set(FLAG_FIELDS) | set(ABILITY_FIELD_NAMES) | {JOB_COMMAND_FIELD_NAME}
)

# ---------------------------------------------------------------------------
# Ability editing (.nxd files, via FF16Tools' nxd-to-sqlite/sqlite-to-nxd).
#
# Unlike JobData/JobCommandData/AbilityData.xml, these aren't shipped by the
# mod loader - they only exist after unpacking the actual game, and the
# resulting .nxd files are FULL replacements when a mod overrides them
# (there's no sparse-diff convention like the XML tables have).
#
# Schema below is verified directly against a real fft_data.sqlite (not
# guessed): table/column names, types, and the Flags12/Flags34/Element bit
# semantics all confirmed against actual data. Bit-packing logic (inversion,
# bit order) ported from Zodi's own flag_codex.html tool, itself verified
# against FFTPatcher's source (Glain/FFTPatcher AbilityAttributes.cs).
# ---------------------------------------------------------------------------

NXD_LANGUAGES = ["en", "ja", "de", "fr", "cs", "ct", "ko"]
NXD_LANGUAGE_LABELS = {
    "en": "English",
    "ja": "Japanese",
    "de": "German",
    "fr": "French",
    "cs": "Chinese (Simplified)",
    "ct": "Chinese (Traditional)",
    "ko": "Korean",
}
NXD_DEFAULT_LANGUAGE = "en"

# Filenames as they appear in the game's unpacked nxd/ folder.
NXD_ABILITY_FILENAMES = {lang: f"ability.{lang}.nxd" for lang in NXD_LANGUAGES}
NXD_OVERRIDE_ACTION_FILENAME = "overrideabilityactiondata.nxd"
NXD_ITEM_FILENAMES = {lang: f"item.{lang}.nxd" for lang in NXD_LANGUAGES}
NXD_ALL_FILENAMES = list(NXD_ABILITY_FILENAMES.values()) + [NXD_OVERRIDE_ACTION_FILENAME]
NXD_ALL_ITEM_FILENAMES = list(NXD_ITEM_FILENAMES.values())

# SQLite table names FF16Tools produces (verified against a real fft_data.sqlite).
NXD_ABILITY_TABLE = {lang: f"Ability-{lang}" for lang in NXD_LANGUAGES}
NXD_OVERRIDE_ACTION_TABLE = "OverrideAbilityActionData"
NXD_ITEM_TABLE = {lang: f"Item-{lang}" for lang in NXD_LANGUAGES}

# Fields in the per-language Ability table this tool exposes for editing.
# (Excludes FF16Tools' own "UnknownXX" columns - no documented meaning, so
# editing them honestly isn't possible; excluded rather than guessed at.)
ABILITY_TEXT_FIELDS = ["Name", "Description", "Comment"]
ABILITY_NUMERIC_FIELDS = {
    # name: (min, max, label, help text)
    "IconId": (0, 65535, "Icon ID", "References the ability's icon texture a live preview is below (only ids 0-54 have textures)."),
    "DLCFlags": (0, 2147483647, "DLC Flags", ""),
    "UiId": (0, 65535, "UI ID", ""),
    "UiId2": (0, 65535, "UI ID 2", ""),
    "AbilityReactionVoiceTypeId": (0, 65535, "Reaction Voice Type ID", ""),
    "IsRandomDamage": (0, 1, "Random Damage", "1 = damage varies randomly, 0 = fixed."),
    "IsRandomStatus": (0, 1, "Random Status", "1 = status chance varies randomly, 0 = fixed."),
}
# JpCost1/JpCost2 are edited together as one JP Cost value (0-65535), split
# into low/high bytes on write - same logic as Zodi's flag_codex.html.
ABILITY_JP_COST_MIN = 0
ABILITY_JP_COST_MAX = 65535
# BattleVoiceIds is a JSON int array in the db; edited as comma-separated ids.
# Every remaining column of Ability-<lang>. Ranges from the real 1.5.2
# data - counted, not guessed. Ten columns that existed in the table and
# were editable nowhere; `dev/audit_field_coverage.py` reported them as
# GAPs, which is how they came to be here.
#
# Most are constant across all 512 rows, which is exactly why they were
# never noticed: a column that is zero everywhere looks like padding until
# somebody tries to use it. That is a reason to expose them, not to hide
# them - a modder experimenting is how a column stops being unknown.
ABILITY_UNKNOWN_NUMERIC_FIELDS = {
    "Unknown14": (0, 255),
    "Unknown16": (0, 255),
    "Unknown17": (0, 255),
    "Unknown18": (0, 255),
    "Unknown19": (0, 255),
    "Unknown1A": (0, 255),
    "Unknown30": (0, 255),
    "Unknown34": (0, 65535),
    "Unknown3C": (0, 255),
}

ABILITY_UNKNOWN_FIELD_NOTES = {
    "Unknown14": "0 on all 512 rows in vanilla.",
    "Unknown16": "0 on all 512 rows in vanilla.",
    "Unknown17": "1 on all 512 rows in vanilla.",
    "Unknown18": "0 on all 512 rows in vanilla.",
    "Unknown19": "0 on all 512 rows in vanilla.",
    "Unknown1A": "0 on all 512 rows in vanilla.",
    "Unknown30": "0 or 2 in vanilla.",
    "Unknown34": "0-3210, 81 distinct values in vanilla.",
    "Unknown3C": "0 or 1 in vanilla.",
}

# `Unknown10` is NOT here. It is NULL on every row in the converted
# database - the converter produces no value for it at all - so there is
# nothing to show and nothing a written value would round-trip through.
# Recorded in audit_field_coverage.WITHHELD rather than silently skipped.

ABILITY_ARRAY_FIELDS = ["BattleVoiceIds"]

ABILITY_FIELD_ORDER = [
    "Name", "Description", "IconId", "JpCost",
    "IsRandomDamage", "IsRandomStatus", "DLCFlags",
    "UiId", "UiId2", "AbilityReactionVoiceTypeId", "BattleVoiceIds", "Comment",
]

# --- OverrideAbilityActionData: language-independent, shared across all locales ---

# Scalar fields that default to -1 ("inherit vanilla/hardcoded behavior") and
# accept 0-255 to override. Labels stay close to the layout's own field
# names since there's no deeper documented meaning to draw from honestly.
OVERRIDE_SCALAR_FIELDS = {
    # name: (min, max, label, help text)
    "Range": (0, 255, "Range", ""),
    "EffectArea": (0, 255, "Effect Area", "AoE radius override."),
    "Vertical": (0, 255, "Vertical Tolerance", ""),
    # "Formula", not "Formula ID": the Items page calls the same field
    # Formula, and two names for one concept is two things to learn.
    "Formula": (0, 255, "Formula", ""),
    "X": (0, 255, "X", ""),
    "Y": (0, 255, "Y", ""),
    "InflictStatus": (0, 255, "Inflict Status", ""),
    "CT": (0, 255, "CT (Charge Time)", ""),
    "MPCost": (0, 255, "MP Cost", ""),
}
# Numeric-spinner override fields shown in the UI (Element is also a plain
# override column in the table, but gets its own checkbox-based UI - see
# OVERRIDE_ALL_COLUMNS below for the full read/write column list).
# Inflict Status follows Formula, because Formula is what decides
# whether it means a status row or a spell to cast.
OVERRIDE_SCALAR_FIELD_ORDER = ["Range", "EffectArea", "Vertical", "Formula", "InflictStatus", "X", "Y", "CT", "MPCost"]
# Every plain int column in OverrideAbilityActionData (matches table order),
# used for reading/writing - Element included, since it's stored the same
# way as the others (just presented differently in the UI).
OVERRIDE_ALL_COLUMNS = ["Range", "EffectArea", "Vertical", "Element", "Formula", "X", "Y", "InflictStatus", "CT", "MPCost"]
OVERRIDE_NOT_SET = -1  # the sentinel meaning "don't override, use vanilla/hardcoded behavior"

# Ability Flags I-IV: 32 individual bits across 4 bytes (Flags12=[byte0,byte1],
# Flags34=[byte2,byte3]). Order within each byte matters: row 0 is bit 7 (MSB),
# row 7 is bit 0 (LSB) - ported exactly from flag_codex.html's computeFlagsetByte.
# "inverted" flags are stored as the opposite bit (checking the box clears it).
ABILITY_FLAG_DEFS = [
    # (id, label, group_index 0-3, inverted, blank/unused)
    ("forceSelfTarget", "Force Self-Target", 0, False, False),
    ("blank7", "", 0, False, True),
    ("weaponRange", "Weapon Range", 0, False, False),
    ("verticalFixed", "Linear Range", 0, False, False),
    ("verticalTolerance", "Vertical Tolerance", 0, False, False),
    ("weaponStrike", "Weapon Strike", 0, False, False),
    ("auto", "Auto", 0, False, False),
    ("targetSelf", "Target Self", 0, True, False),

    ("hitEnemies", "Hit Enemies", 1, True, False),
    ("hitAllies", "Hit Allies", 1, True, False),
    ("topDownTarget", "Top-Down Target", 1, False, False),
    ("followTarget", "Follow Target", 1, True, False),
    ("randomFire", "Random Fire", 1, False, False),
    ("linearAttack", "Linear AoE", 1, False, False),
    ("threeDirections", "3 Directions", 1, False, False),
    ("hitCaster", "Hit Caster", 1, True, False),

    ("reflect", "Reflect", 2, False, False),
    ("arithmetick", "Arithmeticks", 2, False, False),
    ("silence", "Silence", 2, True, False),
    ("mimic", "Mimic", 2, True, False),
    ("normalAttack", "Normal Attack?", 2, False, False),
    ("perservere", "Persevere", 2, False, False),
    ("showQuote", "Quote", 2, False, False),
    ("animateMiss", "Animate on miss", 2, False, False),

    ("counterFlood", "Nature's Wrath", 3, False, False),
    ("counterMagic", "Counter Magic", 3, False, False),
    ("direct", "Direct", 3, False, False),
    ("shirahadori", "Shirahadori", 3, False, False),
    ("requiresSword", "Requires Sword", 3, False, False),
    ("requiresMateriaBlade", "Requires Materia Blade", 3, False, False),
    ("evadeable", "Evadeable", 3, False, False),
    ("targeting", "Targeting", 3, True, False),
]
ABILITY_FLAG_GROUP_LABELS = ["Flagset I", "Flagset II", "Flagset III", "Flagset IV"]

# Element bitmask - same 8 values/order as Job Data's ELEMENT_FLAGS.
ABILITY_ELEMENT_VALUES = [
    ("Fire", 128), ("Lightning", 64), ("Ice", 32), ("Wind", 16),
    ("Earth", 8), ("Water", 4), ("Holy", 2), ("Dark", 1),
]

# =============================================================================
# Items - ItemData.xml (base table) + 5 "Additional Data" tables, keyed by
# TypeFlags -> AdditionalDataId (ItemWeaponData/ItemArmorData/ItemShieldData/
# ItemAccessoryData/ItemEquipBonusData), + ItemShopsData.xml (independent,
# keyed by the same Id as ItemData). All six are plain diff-XML tables, same
# include/inherit-per-field convention as JobData.xml/JobCommandData.xml -
# see item_xml_io.py. Per-language item names/descriptions are a separate,
# much simpler nxd table (Item-xx - no OverrideAbilityActionData-style
# companion table exists for items), see nxd_data.py.
#
# Every enum list below has been cross-checked against the real
# ITEM_*_DATA.cs struct sources (fftivc.utility.modloader, provided
# directly as Structures.zip) - not just sampled from the shipped reference
# XML, which turned out to matter: ItemShopAvailability's real enum has 21
# members but the reference XML only exercises 17 of them, and
# ItemTypeFlags has an extra real bit (ImmuneToStealBreak) plus one
# genuinely-unused bit that no current item sets.
#
# ItemConsumableData.xml still isn't among the tables provided, so an
# "Item"-category consumable's RECOVERY effects can't be edited here - only
# its base ItemData.xml row and nxd name/description.
#
# ItemOptionsData.xml no longer belongs in that sentence. Its inflicted
# statuses have their own Inflict Status tab, built on the derived spec
# rather than a hand-written one: the mod loader's own `ItemOptions` model
# is bundled and declares the field order, the types and the `Effects` flag
# enum, so there is nothing here to restate. `MAX_ITEM_OPTIONS_ID` is not
# declared below for the same reason - `derive_spec` reads 127 from the
# table's own rows.
# =============================================================================

MAX_ITEM_ID = 260              # ItemData.xml: 261 slots (0-260)
MAX_ITEM_WEAPON_ID = 127        # ItemWeaponData.xml: 128 slots
MAX_ITEM_ARMOR_ID = 63          # ItemArmorData.xml: 64 slots (shared by Headgear- and Armor-typed items)
MAX_ITEM_SHIELD_ID = 15         # ItemShieldData.xml: 16 slots
MAX_ITEM_ACCESSORY_ID = 31      # ItemAccessoryData.xml: 32 slots
MAX_ITEM_EQUIP_BONUS_ID = 84    # ItemEquipBonusData.xml: 85 slots
MAX_ITEM_SHOPS_ID = 255         # ItemShopsData.xml: 256 slots (same Id as ItemData)

ITEM_FIELD_ORDER = [
    "Palette", "SpriteID", "RequiredLevel", "TypeFlags", "AdditionalDataId",
    "ItemCategory", "Unused_0x06", "EquipBonusId", "Price", "ShopAvailability", "Unused_0x0B",
]

# TypeFlags: which base equip type (if any) this item is, plus independent
# modifier bits. Exactly one of Weapon/Shield/Headgear/Armor/Accessory
# determines which table AdditionalDataId links into; items with none of
# those five (potions, key items) have no linked Additional Data table.
# Confirmed against the real ITEM_COMMON_DATA.cs struct (Structures.zip):
# ImmuneToStealBreak and the unused bit were never used by any of the 261
# real items sampled, but are real/possible bits in the byte.
ITEM_TYPE_FLAGS = ["Weapon", "Shield", "Headgear", "Armor", "Accessory", "Rare", "ImmuneToStealBreak"]

# TypeFlags value -> which Additional Data table AdditionalDataId points
# into. Headgear and Armor share ItemArmorData.xml (identical HPBonus/
# MPBonus shape) despite being distinct TypeFlags.
ITEM_TYPE_TO_ADDITIONAL_TABLE = {
    "Weapon": "weapon",
    "Shield": "shield",
    "Headgear": "armor",
    "Armor": "armor",
    "Accessory": "accessory",
}

# ItemCategory - confirmed complete and in this exact order against the real
# ITEM_COMMON_DATA.cs struct (Structures.zip).
ITEM_CATEGORIES = [
    "None",
    "Knife", "NinjaBlade", "Sword", "KnightSword", "Katana", "Axe", "Rod", "Staff",
    "Flail", "Gun", "Crossbow", "Bow", "Instrument", "Book", "Polearm", "Pole", "Bag", "Cloth",
    "Shield",
    "Helmet", "Hat", "HairAdornment",
    "Armor", "Clothing", "Robe", "Shoes", "Armguard", "Ring", "Armlet", "Cloak", "Perfume",
    "Throwing", "Bomb",
    "Item",
]

# Story-progress gating for when an item appears in shops (single-select,
# unlike the other Item*Data flag fields). Confirmed complete and in this
# exact order against the real ITEM_COMMON_DATA.cs struct (Structures.zip) -
# the shipped reference XML only exercises 17 of these 21 values, so
# Chapter4_KillZalbag/Unknown17/Unknown18/Unknown19 would have been missed
# without the struct source.
ITEM_SHOP_AVAILABILITY = [
    "Blank",
    "Chapter1_Start", "Chapter1_EnterIgros", "Chapter1_SaveElmdor", "Chapter1_KillMiluda",
    "Chapter2_Start", "Chapter2_SaveOvelia", "Chapter2_MeetDraclau", "Chapter2_SaveAgrias",
    "Chapter3_Start", "Chapter3_Zalmo", "Chapter3_MeetVelius", "Chapter3_SaveRafa",
    "Chapter4_Start", "Chapter4_Bethla", "Chapter4_KillElmdor", "Chapter4_KillZalbag",
    "Unknown17", "Unknown18", "Unknown19", "Unknown20",
]

# Inflict Status sits next to Formula because Formula is what decides
# whether it means a status row or an ability to cast. Reading them
# five rows apart asked the person to hold one to check the other.
ITEM_WEAPON_FIELD_ORDER = ["Range", "AttackFlags", "Formula", "OptionsAbilityId", "Unused_0x03", "Power", "Evasion", "Elements"]
# Confirmed against the real ITEM_WEAPON_DATA.cs struct (Structures.zip),
# ordered high-bit-first to match.
ITEM_ATTACK_FLAGS = ["Striking", "Lunging", "Direct", "Arc", "TwoSwords", "TwoHands", "Throwable", "ForcedTwoHands"]

# Bounds/labels/help text for every plain numeric field across all six
# Item*Data.xml tables (all are single unsigned bytes except Price, a
# ushort - confirmed against the real structs in Structures.zip). Shared
# field names (PhysicalEvasion/MagicalEvasion appear in both ItemShieldData
# and ItemAccessoryData; HPBonus/MPBonus is just ItemArmorData) reuse one
# entry since the bounds/meaning are identical either way.
ITEM_XML_NUMERIC_FIELDS = {
    "Palette": (0, 255, "Palette", "Known issue: Palette is not currently working correctly in The Ivalice Chronicles - edits here may not show up in-game as expected."),
    "SpriteID": (0, 255, "Sprite Id", "Known issue: Sprite Id is not currently working correctly in The Ivalice Chronicles - edits here may not show up in-game as expected."),
    "RequiredLevel": (0, 255, "Required Level", ""),
    "Price": (0, 65535, "Price", ""),
    "AdditionalDataId": (0, 255, "Additional Data Id", "Which row of the linked table below this item uses."),
    "EquipBonusId": (0, 255, "Equip Bonus", ""),
    "Unused_0x06": (0, 255, "Unused_0x06", ""),
    "Unused_0x0B": (0, 255, "Unused_0x0B", ""),
    "Range": (0, 255, "Range", ""),
    "Formula": (0, 255, "Formula", "References the game's internal damage formula table - see https://ffhacktics.com/wiki/Formulas (PSP reference; Ivalice Chronicles may differ)."),
    "Unused_0x03": (0, 255, "Unused_0x03", ""),
    "Power": (0, 255, "Power", ""),
    "Evasion": (0, 255, "Evasion", ""),
    "OptionsAbilityId": (0, 255, "Inflict Status", ""),
    "HPBonus": (0, 255, "HP Bonus", ""),
    "MPBonus": (0, 255, "MP Bonus", ""),
    "PhysicalEvasion": (0, 255, "Physical Evasion", ""),
    "MagicalEvasion": (0, 255, "Magical Evasion", ""),
    "PABonus": (0, 255, "PA Bonus", ""),
    "MABonus": (0, 255, "MA Bonus", ""),
    "SpeedBonus": (0, 255, "Speed Bonus", ""),
    "MoveBonus": (0, 255, "Move Bonus", ""),
    "JumpBonus": (0, 255, "Jump Bonus", ""),
}

ITEM_ARMOR_FIELD_ORDER = ["HPBonus", "MPBonus"]
ITEM_SHIELD_FIELD_ORDER = ["PhysicalEvasion", "MagicalEvasion"]
ITEM_ACCESSORY_FIELD_ORDER = ["PhysicalEvasion", "MagicalEvasion"]

ITEM_EQUIP_BONUS_FIELD_ORDER = [
    "PABonus", "MABonus", "SpeedBonus", "MoveBonus", "JumpBonus",
    "InnateStatus", "ImmuneStatus", "StartingStatus",
    "AbsorbElements", "NullifyElements", "HalveElements", "WeakElements", "StrongElements",
    "BoostJP",
]

ITEM_SHOPS_FIELD_ORDER = ["Shops"]
# The 15 real towns (ItemShopsData.xml's own header comment lists "None"
# as the 16th - that's the empty-selection state, same convention as
# ELEMENT_FLAGS/STATUS_FLAGS not listing "None" as a flag itself).
ITEM_SHOPS = [
    "Gollund", "Dorter", "Zaland", "Goug", "Warjilis", "Bervenia", "SalGhidos",
    "Lesalia", "Riovanes", "Eagrose", "Lionel", "Limberry", "Zeltennia", "Gariland", "Yardrow",
]

# Item-xx nxd table (per-language) - see nxd_data.py. No JP Cost/BattleVoice/
# override-companion-table concept here, much simpler than Abilities.
ITEM_TEXT_FIELDS = ["Name", "NameSingular", "NamePlural", "Description", "Name2", "Comment"]
ITEM_NUMERIC_FIELDS = {
    # name: (min, max, label, help text)
    "DLCFlags": (0, 255, "DLC Flags", ""),
    "Unknown18": (0, 255, "Unknown18", ""),
    "Unknown19": (0, 255, "Unknown19", ""),
    "Unknown1A": (0, 255, "Unknown1A", ""),
    "Unknown1B": (0, 255, "Unknown1B", ""),
    "UiStatusEffectId": (0, 65535, "UI Status Effect Id", "References the status effect shown in the item's tooltip, if any."),
    "UiItemCategoryId": (0, 255, "UI Item Category Id", "Which category header the item is listed under in menus."),
    "SortOrder": (0, 65535, "Sort Order", "Where the item falls in sorted menu lists."),
    "Unknown2C": (0, 255, "Unknown2C", ""),
}
ITEM_BOOL_FIELDS = {
    "IsRandomDamage": ("Random Damage", "1 = damage varies randomly, 0 = fixed."),
}

# =============================================================================
# Encounters - OverrideEntryData (a single shared table, keyed by (Key, Key2)
# - Key is the encounter/ENTD id, Key2 is the unit slot 0-15 within it,
# matching FFTPatcher's ENTD tab) + CharaName-xx (per-language unit names,
# same simple nxd shape as Item-xx/Ability-xx). See nxd_data.py and
# HANDOFF.md for the full picture.
#
# THIS TABLE IS A PATCH LIST, NOT A DATA TABLE. That framing comes straight
# from Nenkai's own OverrideEntryData.layout, which documents a per-column
# *patch condition* rather than a plain type - e.g.
#
#   add_column|MainJob|uint     // 10 - if not zero, it's cast to byte and
#                               //      patches that respective field
#   add_column|JobUnlock|uint   // 14 - if not 20, ...
#
# So every column has a value that means "leave the game's own value
# alone", and CRUCIALLY it is *not* -1 everywhere. It is 0 for some fields,
# 20 for JobUnlock, 255 for others. ENTRY_INHERIT_VALUES below is the
# single source of truth for that, and both the UI's "Inherit / Not Set"
# labels and nxd_data's new-row defaults read from it. Getting this wrong
# is not cosmetic: a row filled with -1 tells the game to patch Spriteset
# to 255, set every UnknownFlags bit, and (via Disable, where any non-zero
# value suppresses the entire rest of the row) disable the unit outright.
#
# Unlike Abilities/Items, there's no full "vanilla reference table" for
# this one - OverrideEntryData is itself a sparse override store (much like
# OverrideAbilityActionData), and no separate base ENTD table was ever
# provided to establish the true valid Key range, so MAX_ENTRY_KEY below is
# a generous bound (matching the highest Key actually observed in real
# data) rather than a confirmed hard limit - FFTPatcher's own ENTD tab is
# the authority on what encounter a given Key corresponds to (see Zodi's
# own notes, OverrideEntryDataNotes.txt, bundled as data/
# OverrideEntryDataNotes.txt).
#
# ---------------------------------------------------------------------------
# Confidence tiers (ENTRY_FIELD_CONFIDENCE below states these per field, and
# the Encounters tab renders them, so a guess never reads as a fact):
#
#   "confirmed" - stated by OverrideEntryData.layout and/or Zodi's own
#                 notes. The strongest evidence available for this table.
#   "inferred"  - not stated anywhere, but strongly implied by the field
#                 name plus the range of values real rows actually carry
#                 (e.g. the equipment slots hold real ItemData ids).
#   "unknown"   - genuinely not known. Exposed as a plain numeric field
#                 with no invented meaning, the same convention Ability's
#                 Unknown18-1B and Item's Unused_0x06 already follow.
#
# A field can be confirmed *mechanically* and unknown *semantically* -
# Unknown8F/90/93-97 are the clearest case: the layout confirms each one
# sets a specific bit of UnknownFlags (so they are genuinely booleans, and
# are checkboxes here), while what those bits actually do is unknown. Those
# are marked "confirmed" for shape and say so in their help text.
# =============================================================================

MAX_ENTRY_KEY = 511    # generous bound - highest Key observed in real data is 500
MAX_ENTRY_KEY2 = 15    # unit slot within an encounter, matches FFTPatcher's 16-unit ENTD convention

ENTRY_FIELD_ORDER = [
    "Unknown00", "Unknown04", "Spriteset", "Unknown4", "MainJob", "JobUnlock",
    "EntryUnknown1D", "SecondarySkillset", "Reaction", "Support", "Movement",
    "Head", "Body", "Accessory", "RightHand", "LeftHand", "InitialDirection",
    "UnitId+characontrolid+Id", "Present",
    "Unknown4C", "Unknown54", "Unknown5C", "Unknown64", "Unknown6C", "Unknown74",
    "Level", "JobLevel", "Unknown80", "Unknown81", "Bravery", "Faith",
    "Unknown86", "Unknown87", "PositionX", "PositionY", "HigherElevation", "Disable",
    "Unknown8E", "Unknown8F", "Unknown90", "Unknown91", "Unknown92", "Unknown93",
    "Unknown94", "Unknown95", "Unknown96", "Unknown97", "LoadFormation", "Unknown99",
    "Unknown9A", "Unknown9B", "Unknown9C",
]

# The 6 TEXT columns that hold JSON-encoded integer arrays (same convention
# as Ability's BattleVoiceIds) - exposed as plain comma-separated-number
# fields since their exact length/meaning isn't confirmed (Unknown5C/64/74
# are usually 3 numbers when set, possibly a per-axis or per-channel
# modifier of some kind, but that's a guess, not confirmed).
# CONFIRMED against Nenkai's OverrideEntryData.layout, which declares the
# real column types. Unknown04 is NOT one of these: it is `string` (offset
# 0x04), and was almost certainly grouped here by confusion with the
# similarly-named Unknown4C. Treating it as an array made every write turn
# its NULL into "[]", silently altering rows the user never touched -
# caught by byte-comparing a real exported mod against its original.
#
# The genuine arrays, with their declared types:
#   Unknown4C int[]   Unknown54 int[]
#   Unknown5C short[] Unknown64 short[] Unknown6C short[] Unknown74 short[]
ENTRY_ARRAY_FIELDS = ["Unknown4C", "Unknown54", "Unknown5C", "Unknown64", "Unknown6C", "Unknown74"]

# Text columns in OverrideEntryData. Declared `string` in the layout, so
# they must round-trip as-is (including NULL) rather than being coerced.
ENTRY_STRING_FIELDS = ["Unknown04"]

# -----------------------------------------------------------------------------
# The "leave the game's own value alone" value, per field.
#
# name -> (value, human wording). Every entry here is taken directly from
# the patch condition OverrideEntryData.layout states for that column; the
# two exceptions are marked INFERRED in their wording and in
# ENTRY_FIELD_CONFIDENCE. Fields absent from this dict have no documented
# patch condition at all - they are not given an invented one.
#
# Real-data cross-check (516 vanilla rows), which agrees with every entry:
#   Spriteset 0 in 512    MainJob 0 in 501     JobUnlock 20 in 503
#   InitialDirection 255 in 513                Present 255 in 515
#   HigherElevation 255 in 511                 Disable 0 in 516
#   EntryUnknown1D/Bravery/Faith/Accessory/LeftHand -1 in all 516
# -----------------------------------------------------------------------------
ENTRY_INHERIT_VALUES = {
    "Spriteset": (0, "0 = leave the unit's own sprite set alone (the layout only patches this when it isn't zero)."),
    # The layout gives Unknown4 no patch condition at all ("?? "), but
    # Zodi verified in-game that setting this really does change the unit's
    # displayed name, and 476 of 516 vanilla rows carry 0 - so 0 is the
    # "no override" value. Confirmed by testing rather than by the layout.
    "Unknown4": (0, "0 = no unit-name override."),
    "MainJob": (0, "0 = leave the unit's own job alone. Note this also means job id 0 cannot be forced through this table."),
    "JobUnlock": (20, "20 = leave job unlocks alone. This is the one field whose \u201cinherit\u201d value is neither 0 nor -1."),
    "EntryUnknown1D": (-1, "-1 = leave the unit's own primary job command alone."),
    "SecondarySkillset": (-1, "-1 = leave the unit's own secondary job command alone."),
    "Reaction": (-1, "-1 = leave the unit's own reaction ability alone."),
    "Support": (-1, "-1 = leave the unit's own support ability alone."),
    "Movement": (-1, "-1 = leave the unit's own movement ability alone."),
    "Head": (-1, "-1 = leave this equipment slot alone."),
    "Body": (-1, "-1 = leave this equipment slot alone."),
    "Accessory": (-1, "-1 = leave this equipment slot alone."),
    "RightHand": (-1, "-1 = leave this equipment slot alone."),
    "LeftHand": (-1, "-1 = leave this equipment slot alone."),
    "InitialDirection": (255, "255 = leave the unit's own facing alone."),
    "UnitId+characontrolid+Id": (0, "0 = no override."),
    "Present": (255, "255 = leave the unit's own presence flags alone."),
    "Level": (-1, "-1 (in fact any value of 0 or less) = leave the unit's own level alone."),
    "JobLevel": (-1, "-1 (in fact any value of 0 or less) = leave the unit's own job level alone."),
    "Bravery": (-1, "-1 = leave the unit's own Bravery alone."),
    "Faith": (-1, "-1 = leave the unit's own Faith alone."),
    "PositionX": (-1, "-1 = leave the unit's own starting position alone."),
    "PositionY": (-1, "-1 = leave the unit's own starting position alone."),
    "HigherElevation": (255, "255 (in fact anything other than 0 or 1) = leave the unit's own elevation alone."),
    "Disable": (0, "0 = normal. ANY other value disables the unit and suppresses every other patch on this row."),
    # Every UnknownFlags bit field, plus LoadFormation: the layout's
    # condition is "if not zero", so 0 is the inherit value for all of them.
    "Unknown8E": (0, "0 = off."),
    "Unknown8F": (0, "0 = off."),
    "Unknown90": (0, "0 = off."),
    "Unknown91": (0, "0 = off."),
    "Unknown92": (0, "0 = off."),
    "Unknown93": (0, "0 = off."),
    "Unknown94": (0, "0 = off."),
    "Unknown95": (0, "0 = off."),
    "Unknown96": (0, "0 = off."),
    "Unknown97": (0, "0 = off."),
    "Unknown99": (0, "0 = off."),
    "LoadFormation": (0, "0 = off."),
}

# Fields with no documented patch condition. A brand-new row uses 0 for
# these (what every vanilla row carries, for all of them except Unknown80/
# 81/9C, which carry 0 in the large majority) rather than -1, because -1
# stored in a byte column reads back as 255 and would trip any "if not
# zero" condition these might turn out to have.
ENTRY_NO_DOCUMENTED_SENTINEL = [
    "Unknown00", "Unknown80", "Unknown81", "Unknown86", "Unknown87",
    "Unknown9A", "Unknown9B", "Unknown9C",
]

# Equipment/job/job-command fields the layout says are "cast to byte"
# before being applied. Ids above 255 therefore cannot be reached through
# this table at all - real and relevant, since ItemData runs 0-260 and
# JobCommandData runs 0-226. The Encounters tab marks unreachable choices
# rather than silently offering them.
ENTRY_BYTE_CAST_FIELDS = ["MainJob", "JobUnlock", "EntryUnknown1D", "Head", "Body", "Accessory", "RightHand", "LeftHand"]

# ---------------------------------------------------------------------------
# Values that are not ids at all
#
# Each of the twelve id fields in ENTRY_FIELD_LABELS has, besides its own
# inherit value above, a handful of values that mean something rather than
# pointing at a row. They are here beside the inherit values because they
# are the same kind of fact about the same columns, and because the
# Encounters page's dropdowns and its field captions have to agree about
# them - two lists would drift.
#
# Where they come from, and what was checked before building on them:
#
# * Zodi's ruling on 255: "255 is random in the PSP version therefore I
#   will assume that it is also the case for TIC." That was an assumption,
#   so it was measured against the real tables rather than taken on trust,
#   and they support it on every sentinel - there is nothing real at any of
#   these ids to lose:
#       CharaName-en 253, 254 and 255 have NO name (story names run 1-~250,
#           Ramza 1, Ovelia 12, Rapha 25, Alma 48; 256+ are the IsGeneric
#           rows, Arnald, Ivan, Isleton...). 844 of the 1,024 rows are named.
#       ItemData 254 and 255 are blank rows - no name, no category, price 0.
#           Real items resume at 256 ("Materia Blade Plus").
#       ItemData 0 IS a named row, "Nothing Equipped", which is exactly the
#           "0 is nothing" Zodi's own notes give it. The label below says
#           the same thing in the words an encounter row needs.
#
# * 510 rather than 254 on Reaction/Support/Movement is not an
#   inconsistency. Those three are 16-BIT fields in ENTD (bytes 12-13,
#   14-15, 16-17, little-endian), so the 16-bit form of the same 0xFE
#   sentinel is 0x01FE = 510 where a byte field's is 0xFE = 254. Measured
#   in the real ENTD data: 510 appears 7,303 / 7,193 / 7,594 times across
#   the three. It never appears in the vanilla OverrideEntryData table
#   (Movement tops out at 509), so it is offered on the strength of ENTD's
#   own usage and the PSP behaviour rather than on a sighting there.
# ---------------------------------------------------------------------------

#: Every equipment slot says the same three things, so they are written
#: once. Five near-identical dicts is how the five drift apart.
_ENTRY_EQUIPMENT_SPECIALS = {
    0: "Nothing (Monster)",
    254: "Random",
    255: "Nothing (Human)",
}
_ENTRY_COMMAND_SPECIALS = {
    0: "Nothing",
    254: "Random",
    255: "Job's Command",
}
_ENTRY_RSM_SPECIALS = {
    0: "Nothing",
    510: "Random",
}

ENTRY_SPECIAL_VALUES: dict[str, dict[int, str]] = {
    "Unknown4": {255: "Random"},
    "EntryUnknown1D": dict(_ENTRY_COMMAND_SPECIALS),
    "SecondarySkillset": dict(_ENTRY_COMMAND_SPECIALS),
    "Reaction": dict(_ENTRY_RSM_SPECIALS),
    "Support": dict(_ENTRY_RSM_SPECIALS),
    "Movement": dict(_ENTRY_RSM_SPECIALS),
    "Head": dict(_ENTRY_EQUIPMENT_SPECIALS),
    "Body": dict(_ENTRY_EQUIPMENT_SPECIALS),
    "Accessory": dict(_ENTRY_EQUIPMENT_SPECIALS),
    "RightHand": dict(_ENTRY_EQUIPMENT_SPECIALS),
    "LeftHand": dict(_ENTRY_EQUIPMENT_SPECIALS),
    # MainJob has none. Its inherit value is 0, and no other value on it
    # means anything but "this job id".
    "MainJob": {},
}

# No special value may sit on top of its own field's inherit value.
#
# This assertion is the one with teeth. The obvious reading of this table -
# "0 means Inherit, like Unit Name and Main Job" - is wrong on the other ten
# fields, where inherit is -1 and 0 is a real and different answer
# ("Nothing"). Merging the two would tell the game "equip nothing" where the
# mod author meant "leave this alone", on ten fields at once, and nothing on
# screen would say so. It is the same confusion the NumericFieldRow floor
# logic in encounters.py was added to prevent.
#
# The companion check - that this table covers exactly the twelve id fields -
# is beside ENTRY_FIELD_LABELS, which is defined further down this file.
assert not [
    field for field, specials in ENTRY_SPECIAL_VALUES.items()
    if ENTRY_INHERIT_VALUES.get(field, (None,))[0] in specials
], "a special value collides with that field's own inherit value"

# ---------------------------------------------------------------------------
# The six fields that hold a VALUE with a fixed meaning
#
# Different in kind from the twelve above, which point at a row in another
# table. These six hold a number the game reads directly - a level, a
# facing, which job has to be unlocked - and every legal value has a
# meaning, so the whole domain can be offered as a list.
#
# "on the Encounters page, for the Job Unlock field can we change it into a
# drop down so that 0 = Base, 1 = Chemist ... 20 = Inherit", and "can we
# turn Spriteset (called Unit in FFTPatcher), Level, Bravery, Faith, and
# Initial Direction into a drop down matching FFTPatcher."
#
# Each number below was measured against the real data before being
# written here - the four ENTD files (7,829 occupied slots) and the 516
# vanilla OverrideEntryData rows. The measurements are in HANDOFF.md.
# ---------------------------------------------------------------------------

#: Which six. A tuple and not a name->label dict, deliberately: all six are
#: already in ENTRY_NUMERIC_FIELDS, which is where their labels live and
#: where the page reads them from. A second column of "Job Unlock", "Initial
#: Direction" here would be a second set of words for the same six fields,
#: and the one that gets edited is never the one being read.
#:
#: What this table IS for is the question ENTRY_FIELD_LABELS answers for the
#: other twelve: is this field a list of rows in another table, or a list of
#: values? The answer decides where its names come from, and the two sets
#: must not overlap.
ENTRY_VALUE_FIELDS = (
    "JobUnlock", "Spriteset", "Level", "JobLevel", "Bravery", "Faith",
    "InitialDirection",
)

#: 254 means "roll it" on the three columns that accept it. Stated here as
#: well as in `entd.RANDOM_BYTE` because the two modules must not import
#: each other; `dev/test_qt_encounters.py` checks they agree.
ENTRY_RANDOM_VALUE = 254

#: Job Unlock id 1 is job 0x4B and they run consecutively to id 19.
#:
#: From FFTPatcher's own `GetPreReqJobDataSource`, which builds its list as
#: `jobs[0x4B..0x5D]` keyed `index - 0x4A`, and confirmed against this
#: game's job table: 0x4B-0x5D are Chemist, Knight, Archer ... Dancer,
#: Mime, exactly the nineteen Zodi listed.
#:
#: FFTPatcher does NOT stop at 19 - it adds two PSP-only jobs at 20 and 21.
#: Both of those job rows are UNNAMED in this game, Job Unlock spans
#: exactly 0-19 across the ENTD files with all twenty present, and the nxd
#: holds 20 on 503 of its 516 rows. 20 is one past the end and is the
#: inherit value, which is what ENTRY_INHERIT_VALUES already said.
ENTRY_JOB_UNLOCK_FIRST_JOB = 0x4B
ENTRY_JOB_UNLOCK_JOBS = 19

#: Sprite ids 0-130. The game's own `Chara` table is keyed 0-130, 131 rows,
#: and the Spriteset byte across all four ENTD files spans exactly 0-130.
#: FFTPatcher's list runs to 168; those are ids this game has no sprite for.
ENTRY_SPRITESET_COUNT = 131

#: Bravery and Faith are 0-100. FFTPatcher offers exactly that plus Random,
#: and the real data agrees - Bravery never exceeds 95 and Faith never 100.
ENTRY_TRAIT_MAX = 100

#: Level 100 is "Party level" and 101-199 are "Party level + 1" to "+99",
#: which is FFTPatcher's `levelStrings` layout. Real: 473 occupied slots
#: hold 101-130, so the band is in use and is not a quirk of the old tool.
#:
#: 0 is NOT offered. FFTPatcher's ENTD byte reads 0 as "Party level -
#: Random", but the nxd layout's patch condition for this column is
#: "greater than zero", so through this table 0 means inherit and cannot
#: mean anything else. That difference between the two files is why the
#: list here is built rather than copied.
ENTRY_LEVEL_PARTY = 100
ENTRY_LEVEL_MAX = 199

#: Job Level runs 1-8. Asked for as "0 to 8", and 0 is left out for the
#: same reason it is left out of Level: the layout gives this column the
#: ditto of Level's condition -
#:
#:     add_column|Level|short      // 7C - if greater than zero, ...
#:     add_column|JobLevel|short   // 7E - ' '
#:
#: so through the nxd 0 patches nothing and means inherit, which is what
#: the Inherit entry at -1 already says. Offering it twice would put an
#: entry in the list that silently does nothing.
#:
#: 8 is the ceiling in the real data too: the ENTD files span 0-8 and the
#: nxd holds 1, 5, 6, 7 and 8.
ENTRY_JOB_LEVEL_MAX = 8

#: The two columns whose patch condition is "greater than zero", so that
#: **0 inherits on them as surely as -1 does**.
#:
#: Straight out of the layout, where JobLevel takes Level's condition by
#: ditto:
#:
#:     add_column|Level|short      // 7C - if greater than zero, ...
#:     add_column|JobLevel|short   // 7E - ' '
#:
#: `ENTRY_INHERIT_VALUES` has said this in prose since it was written -
#: "-1 (in fact any value of 0 or less)" - and nothing could act on prose.
#: Anything deciding whether a field is inheriting has to ask this too, or
#: it reads a stored 0 on these two as a real value.
ENTRY_POSITIVE_ONLY_FIELDS = ("Level", "JobLevel")

# Both are real columns with a documented sentinel, and the wording above
# is where this came from - so if one of them ever loses its entry there,
# this tuple is naming a column nothing knows about.
assert all(field in ENTRY_INHERIT_VALUES
           for field in ENTRY_POSITIVE_ONLY_FIELDS), (
    "ENTRY_POSITIVE_ONLY_FIELDS names a column with no inherit value: "
    f"{[f for f in ENTRY_POSITIVE_ONLY_FIELDS if f not in ENTRY_INHERIT_VALUES]}")
assert all("0 or less" in ENTRY_INHERIT_VALUES[field][1]
           for field in ENTRY_POSITIVE_ONLY_FIELDS), (
    "a column here no longer says '0 or less' in its own help text, so "
    "either the layout changed or this tuple is wrong")

#: The values that are not a plain number, per field. Read through
#: `entry_special_values` alongside the twelve id fields' table, so the
#: dropdown entry and the Inherit entry for the same value cannot disagree.
ENTRY_VALUE_SPECIALS: dict[str, dict[int, str]] = {
    # 0 is not job 0x4A. FFTPatcher calls it Base and so does Zodi's list.
    "JobUnlock": {0: "Base"},
    # FFTPatcher's own name for it, which says what it randomises rather
    # than only that it does. Its `levelStrings` calls byte 254 "Party
    # level - Random"; "Random" alone reads as "a random level 1-99".
    "Level": {ENTRY_RANDOM_VALUE: "Party Level - Random"},
    # Job Level has no value that is not a plain job level.
    "JobLevel": {},
    "Bravery": {ENTRY_RANDOM_VALUE: "Random"},
    "Faith": {ENTRY_RANDOM_VALUE: "Random"},
    # Spriteset and Initial Direction have none: every value in their lists
    # is a name for that number, not an escape from it.
    "Spriteset": {},
    "InitialDirection": {},
}

# The same two rules the twelve id fields' table carries, for the same
# reasons. A special sitting on a field's own inherit value would merge
# "leave this alone" with a real answer; a field in one table and not the
# other would be a dropdown with no specials or specials with no dropdown.
assert set(ENTRY_VALUE_SPECIALS) == set(ENTRY_VALUE_FIELDS), (
    "ENTRY_VALUE_SPECIALS and ENTRY_VALUE_FIELDS must cover the same six "
    f"fields; these appear in one but not the other: "
    f"{sorted(set(ENTRY_VALUE_SPECIALS) ^ set(ENTRY_VALUE_FIELDS))}")
assert not [
    field for field, specials in ENTRY_VALUE_SPECIALS.items()
    if ENTRY_INHERIT_VALUES.get(field, (None,))[0] in specials
], "a value field's special collides with its own inherit value"
assert not set(ENTRY_VALUE_SPECIALS) & set(ENTRY_SPECIAL_VALUES), (
    "a field cannot be both a list of rows and a list of values: "
    f"{sorted(set(ENTRY_VALUE_SPECIALS) & set(ENTRY_SPECIAL_VALUES))}")


def entry_level_choices() -> dict:
    """
    `{value: what it reads}` for the Level column, 1-199 plus Random.

    Built rather than written out, because 199 lines of "Party level + 62"
    is 199 chances to typo one. The two facts it is built from -
    `ENTRY_LEVEL_PARTY` and `ENTRY_LEVEL_MAX` - are stated above with what
    was measured.
    """
    found = {level: str(level) for level in range(1, ENTRY_LEVEL_PARTY)}
    found[ENTRY_LEVEL_PARTY] = "Party level"
    for level in range(ENTRY_LEVEL_PARTY + 1, ENTRY_LEVEL_MAX + 1):
        found[level] = f"Party level + {level - ENTRY_LEVEL_PARTY}"
    return found


# Present is a bitmask patch, not a checkbox. The layout: "if not 255, it's
# cast to byte and patches that respective field with the mask 0xC
# (b00001100)". Real modded data settles it - Zodi's own Dark Knight
# Expansion rows carry 148, 84, 100 and 164, none of which is 0 or 255.
# Modelling this as a checkbox (255 = ticked, 0 = unticked, as this tab did
# until now) displayed all four of those as "unticked" and rewrote them to
# 0 or 255 the moment the row was touched - the same silent-rewrite bug
# class as Unknown04. It is a plain 0-255 number now.
ENTRY_PRESENT_INHERIT_VALUE = 255
ENTRY_PRESENT_MASK = 0x0C

# Fields that are genuinely 1/0 flags. Two groups, deliberately kept
# distinguishable in the UI:
#
#  - the four Zodi's own notes explain (8E/91/92/99), where both the shape
#    AND the meaning are known;
#  - the rest (8F/90/93-97, LoadFormation), where the layout confirms the
#    shape - each sets one specific bit of UnknownFlags, and real data only
#    ever holds 0 or 1 - but the meaning is unknown.
#
# name -> (label, help text, meaning_known)
ENTRY_BOOL_FIELDS = {
    "Unknown8E": ("Special Unit Marker + Gold Health Bar", "If checked, this unit has the special-unit marker and a gold health bar. Sets the initial value of UnknownFlags.", True),
    "Unknown91": ("Objective Marker (Top Portrait)", "If checked, this unit has the objective marker on its top portrait. (UnknownFlags bit 3.)", True),
    "Unknown92": ("Objective Marker (Bottom Portrait)", "If checked, this unit has the objective marker on its bottom portrait - overrides Special Unit Marker. (UnknownFlags bit 4.)", True),
    "Unknown99": ("First Turn", "If checked, this unit takes the first turn. (UnknownFlags bit 10.)", True),
    "LoadFormation": ("Load Formation Screen", "If checked, patches the LoadFormation flag, which controls whether the deployment/formation screen is used before this battle.", True),
    "Unknown8F": ("Unknown flag 8F", "Sets UnknownFlags bit 1. Confirmed to be a flag by the layout and by real data (only ever 0 or 1) - what the bit does is unknown.", False),
    "Unknown90": ("Unknown flag 90", "Sets UnknownFlags bit 2. Confirmed to be a flag; effect unknown. Set on 10 vanilla rows.", False),
    "Unknown93": ("Unknown flag 93", "Sets UnknownFlags bit 5. Confirmed to be a flag; effect unknown. Set on 9 vanilla rows.", False),
    "Unknown94": ("Unknown flag 94", "Sets UnknownFlags bit 6. Confirmed to be a flag; effect unknown. Set on 7 vanilla rows.", False),
    "Unknown95": ("Unknown flag 95", "Sets UnknownFlags bit 7. Confirmed to be a flag; effect unknown. Set on 1 vanilla row.", False),
    "Unknown96": ("Unknown flag 96", "Sets UnknownFlags bit 8. Confirmed to be a flag; effect unknown. Set on 1 vanilla row.", False),
    "Unknown97": ("Unknown flag 97", "Sets UnknownFlags bit 9. Confirmed to be a flag; effect unknown. Set on 1 vanilla row.", False),
}

# -----------------------------------------------------------------------------
# The column type each field is DECLARED as in Nenkai's OverrideEntryData.
# layout. Transcribed verbatim from the layout, and the reason it's here is
# that half of these are unsigned: writing -1 into a `uint` or `byte`
# column doesn't mean "inherit", it means 4294967295 / 255 once the game
# reads it back. ENTRY_NUMERIC_BOUNDS below derives each field's editable
# range from this, so the two can't drift apart, and a test asserts it.
#
# `byte` is unsigned in this format (real values run 0-255) even though it
# doesn't start with a "u".
# -----------------------------------------------------------------------------
ENTRY_COLUMN_TYPES = {
    "Unknown00": "int", "Unknown04": "string", "Spriteset": "uint",
    "Unknown4": "uint", "MainJob": "uint", "JobUnlock": "uint",
    "EntryUnknown1D": "int", "SecondarySkillset": "int", "Reaction": "int",
    "Support": "int", "Movement": "int", "Head": "int", "Body": "int",
    "Accessory": "int", "RightHand": "int", "LeftHand": "int",
    "InitialDirection": "int", "UnitId+characontrolid+Id": "int", "Present": "int",
    "Unknown4C": "int[]", "Unknown54": "int[]", "Unknown5C": "short[]",
    "Unknown64": "short[]", "Unknown6C": "short[]", "Unknown74": "short[]",
    "Level": "short", "JobLevel": "short", "Unknown80": "byte", "Unknown81": "byte",
    "Bravery": "short", "Faith": "short", "Unknown86": "byte", "Unknown87": "byte",
    "PositionX": "short", "PositionY": "short", "HigherElevation": "byte",
    "Disable": "byte", "Unknown8E": "byte", "Unknown8F": "byte", "Unknown90": "byte",
    "Unknown91": "byte", "Unknown92": "byte", "Unknown93": "byte", "Unknown94": "byte",
    "Unknown95": "byte", "Unknown96": "byte", "Unknown97": "byte",
    "LoadFormation": "byte", "Unknown99": "byte", "Unknown9A": "byte",
    "Unknown9B": "byte", "Unknown9C": "byte",
}

# Declared type -> the values that type can actually hold.
NEX_TYPE_RANGES = {
    "byte": (0, 255),
    "short": (-32768, 32767),
    "ushort": (0, 65535),
    "int": (-2147483648, 2147483647),
    "uint": (0, 4294967295),
}


def entry_numeric_bounds(field_name: str) -> tuple:
    """
    The editable range for a column, narrowed to what its declared type can
    hold and to what this tool sensibly offers.

    Signed columns get -1 as their floor because that's the "leave it
    alone" value for most of them. Unsigned columns get 0 - offering -1
    there would let someone write a value the game reads back as 255 or
    4294967295, which is how a field that looks like "inherit" ends up
    patching something.
    """
    declared = ENTRY_COLUMN_TYPES.get(field_name, "int")
    low, high = NEX_TYPE_RANGES.get(declared, (-2147483648, 2147483647))
    floor = 0 if low >= 0 else -1
    # 255 is the practical ceiling for everything the game byte-casts;
    # nothing observed in real data needs more, and a wider spinbox just
    # invites values that truncate.
    return (floor, min(high, 255))


# Plain numeric fields: name -> (min, max, label, help text). Bounds come
# from entry_numeric_bounds() so they always match the declared type.
_ENTRY_NUMERIC_TEXT = {
    "Unknown00": ("Unknown00", "The layout marks this column \u201cnot used in game code\u201d. Every vanilla row carries 0."),
    "Spriteset": ("Spriteset", "Which sprite/graphic set this unit uses. Cast to a byte."),
    "JobUnlock": ("Job Unlock", (
        "Index into a separate \"jobs unlocked\" list (not the same numbering as "
        "Main Job) - matches FFTPatcher's ENTD \"Jobs Unlocked\" list: 0 = Squire/"
        "Special Job, 1 = Chemist, 2 = Knight, etc, except Dark Knight, Onion Knight, "
        "and (probably) Unknown, which were removed in The Ivalice Chronicles. Job "
        "Level below only applies if this matches the unit's currently-selected job "
        "(Chemist/Squire are an exception - set this to Mine with Job Level 8, since "
        "those two need to already be Level 8 to unlock Mine anyway). Special units "
        "with a unique job command are treated the same as a Squire."
    )),
    "InitialDirection": ("Initial Direction", "Starting facing direction. Only the lower 4 bits are applied (value & 0xF)."),
    "UnitId+characontrolid+Id": ("Unit/CharaControl Id", (
        "Applied only when non-zero AND a row with that id exists in the game's own "
        "unit table - the UnitId from that row is what gets patched in. What that "
        "table is wasn't established here, so this stays a plain number."
    )),
    "Present": ("Present / Presence Flags", (
        "A bitmask, not a yes/no. Applied through the mask 0xC, so only bits 2 and 3 "
        "take effect and the remaining bits of whatever you enter are ignored. Real mods "
        "use values like 84, 100, 148 and 164 here, which is why this is a plain number "
        "rather than a checkbox."
    )),
    "Level": ("Level", (
        "Like FFTPatcher's ENTD Level field - certain values have special meaning "
        "(matching the party's own level, offsetting above/below it, etc.) rather "
        "than always being a literal level number - see FFTPatcher's ENTD tab for "
        "the exact special values, or set a literal 1-99 for a fixed level. Real mods "
        "use values in the 100s for the party-relative behaviour."
    )),
    "JobLevel": ("Job Level", (
        "Only takes effect (max 8) if Job Unlock matches the unit's currently-"
        "selected job - see Job Unlock's note."
    )),
    "Unknown80": ("Unknown80", "Genuinely unknown. Real rows carry 0 (513) or 255 (3)."),
    "Unknown81": ("Unknown81", "Genuinely unknown. Real rows carry 0 (513) or 255 (3)."),
    "Bravery": ("Bravery", "No vanilla row overrides this."),
    "Faith": ("Faith", "No vanilla row overrides this."),
    "Unknown86": ("Unknown86", "Genuinely unknown. Every vanilla row carries 0."),
    "Unknown87": ("Unknown87", "Genuinely unknown. Every vanilla row carries 0."),
    "PositionX": ("Position X", "Starting battle-grid position."),
    "PositionY": ("Position Y", "Starting battle-grid position."),
    "HigherElevation": ("Higher Elevation", "Patches the uppermost bit of Initial Direction. Only 0 and 1 do anything."),
    "Disable": ("Disable", "Every vanilla row carries 0."),
    "Unknown9A": ("Unknown9A", "The layout guesses \u201cprobably struct padding\u201d. Real rows carry 0 (514) or 1 (2)."),
    "Unknown9B": ("Unknown9B", "The layout guesses \u201cprobably struct padding\u201d. Every vanilla row carries 0."),
    "Unknown9C": ("Unknown9C", (
        "The layout guesses \u201cprobably struct padding\u201d, but real rows hold 94 distinct "
        "values between 0 and 244, which is not what padding usually looks like - "
        "though it is exactly what uninitialised bytes look like too. Left genuinely "
        "unknown rather than resolved either way."
    )),
}

# name -> (min, max, label, help text), with the range derived from the
# column's declared type rather than hand-written per field.
ENTRY_NUMERIC_FIELDS = {
    name: entry_numeric_bounds(name) + text
    for name, text in _ENTRY_NUMERIC_TEXT.items()
}

# The six value fields keep their labels HERE and only here - the companion
# to the note beside ENTRY_VALUE_FIELDS, which is defined earlier in this
# file and so cannot check this itself. They became dropdowns; they did not
# stop being numbers, and "Job Unlock" is still what the row is called.
assert set(ENTRY_VALUE_FIELDS) <= set(ENTRY_NUMERIC_FIELDS), (
    "every value field needs its label and bounds in ENTRY_NUMERIC_FIELDS; "
    f"missing: {sorted(set(ENTRY_VALUE_FIELDS) - set(ENTRY_NUMERIC_FIELDS))}")

# Per-field confidence, rendered in the tab so a guess never reads as a
# fact. See the tier definitions in this section's header comment.
ENTRY_FIELD_CONFIDENCE = {
    # Confirmed - Zodi's own notes and/or the layout's patch condition.
    "Key": "confirmed", "Key2": "confirmed",
    "Unknown4": "confirmed",          # Zodi's notes: the unit's name, from CharaName
    "EntryUnknown1D": "confirmed",    # Zodi's notes: the primary skillset/job command
    "SecondarySkillset": "confirmed",
    "JobUnlock": "confirmed", "Level": "confirmed", "JobLevel": "confirmed",
    "Unknown8E": "confirmed", "Unknown91": "confirmed", "Unknown92": "confirmed",
    "Unknown99": "confirmed", "LoadFormation": "confirmed",
    "Spriteset": "confirmed", "MainJob": "confirmed", "InitialDirection": "confirmed",
    "Present": "confirmed", "HigherElevation": "confirmed", "Disable": "confirmed",
    "Unknown00": "confirmed",         # confirmed *unused*, which is itself a fact
    # Confirmed as flags by the layout, meaning unknown - see ENTRY_BOOL_FIELDS.
    "Unknown8F": "confirmed", "Unknown90": "confirmed", "Unknown93": "confirmed",
    "Unknown94": "confirmed", "Unknown95": "confirmed", "Unknown96": "confirmed",
    "Unknown97": "confirmed",
    # Were "inferred" (field name + observed values). Zodi verified each of
    # them in-game and they behave as labelled, so they are confirmed now -
    # by testing rather than by the layout, which is still confirmation.
    "Reaction": "confirmed", "Support": "confirmed", "Movement": "confirmed",
    "Head": "confirmed", "Body": "confirmed", "Accessory": "confirmed",
    "RightHand": "confirmed", "LeftHand": "confirmed",
    "Bravery": "confirmed", "Faith": "confirmed",
    "PositionX": "confirmed", "PositionY": "confirmed",
    "UnitId+characontrolid+Id": "confirmed",
    # Genuinely unknown.
    "Unknown04": "unknown", "Unknown80": "unknown", "Unknown81": "unknown",
    "Unknown86": "unknown", "Unknown87": "unknown",
    "Unknown9A": "unknown", "Unknown9B": "unknown", "Unknown9C": "unknown",
    "Unknown4C": "unknown", "Unknown54": "unknown", "Unknown5C": "unknown",
    "Unknown64": "unknown", "Unknown6C": "unknown", "Unknown74": "unknown",
}

ENTRY_CONFIDENCE_LABELS = {
    "confirmed": ("Confirmed", "Documented by Nenkai's OverrideEntryData.layout and/or Zodi's own notes."),
    "inferred": ("Inferred", "Not documented anywhere - read from the field name plus the values real rows carry."),
    "unknown": ("Unknown", "Genuinely not known. Shown as a plain value with no invented meaning."),
}

# Fields grouped for the UI - a plain flat list of 50+ fields would be
# unusable, mirrors the Jobs tab's own tabbed-sections approach. Regrouped
# so the sections reflect the layout's own patch groupings: the ten
# UnknownFlags bit fields now sit together (they are one uint in the game's
# memory), and the fields whose meaning is genuinely unknown are collected
# at the bottom rather than salted through the useful ones.
# Section membership and order, both from real use.
#
# The two Job Command fields moved out of Identity and to the TOP of
# Abilities: they pick a command set, which is what the three ability slots
# under them modify, so reading the five together is how somebody actually
# thinks about a unit. Zodi's wording: "change the order of the Abilities
# drop down to be Primary Job Command, Secondary Job Command, Reaction,
# Support, and then Movement."
#
# Equipment leads with the hands because that is what a mod author changes
# first and what decides a unit's whole role - "Right Hand, Left Hand, Head,
# Body, and then Accessory" - rather than running top-to-bottom down the
# body as the ENTD byte order happens to.
ENTRY_FIELD_SECTIONS = {
    "Identity": ["Unknown4", "MainJob", "JobUnlock", "JobLevel", "Spriteset"],
    "Abilities": ["EntryUnknown1D", "SecondarySkillset", "Reaction", "Support", "Movement"],
    "Equipment": ["RightHand", "LeftHand", "Head", "Body", "Accessory"],
    "Stats & Level": ["Level", "Bravery", "Faith"],
    "Placement & Presence": ["PositionX", "PositionY", "InitialDirection", "HigherElevation", "Present", "Disable", "LoadFormation", "UnitId+characontrolid+Id"],
    "Unit Markers & Turn Order (UnknownFlags)": ["Unknown8E", "Unknown8F", "Unknown90", "Unknown91", "Unknown92", "Unknown93", "Unknown94", "Unknown95", "Unknown96", "Unknown97", "Unknown99"],
    "Unknown Fields": ["Unknown00", "Unknown80", "Unknown81", "Unknown86", "Unknown87", "Unknown9A", "Unknown9B", "Unknown9C"],
    "Unknown Data Arrays": ["Unknown04", "Unknown4C", "Unknown54", "Unknown5C", "Unknown64", "Unknown6C", "Unknown74"],
}

# EntryUnknown1D/SecondarySkillset - Zodi's own naming call: "Mod Studio
# calls these Job Commands so I guess later on when a user edits
# SecondarySkillset we should call those Secondary Job Command in Mod
# Studio."
ENTRY_FIELD_LABELS = {
    "Unknown4": "Unit Name",
    "MainJob": "Main Job",
    "EntryUnknown1D": "Primary Job Command",
    "SecondarySkillset": "Secondary Job Command",
    "Reaction": "Reaction",
    "Support": "Support",
    "Movement": "Movement",
    "Head": "Head",
    "Body": "Body",
    "Accessory": "Accessory",
    "RightHand": "Right Hand",
    "LeftHand": "Left Hand",
}

# The twelve id fields are exactly the twelve that have a list of values
# meaning something other than "a row id". Checked here rather than at
# ENTRY_SPECIAL_VALUES only because that table is defined earlier, beside
# the inherit values it must not collide with.
# The eighteen dropdown fields split cleanly in two, and must: a field is
# either a list of rows in another table or a list of values, and where its
# names come from depends on which. Checked here because ENTRY_VALUE_FIELDS
# is defined earlier, beside the inherit values it must not collide with.
assert not set(ENTRY_VALUE_FIELDS) & set(ENTRY_FIELD_LABELS), (
    "a field cannot be both a list of rows and a list of values: "
    f"{sorted(set(ENTRY_VALUE_FIELDS) & set(ENTRY_FIELD_LABELS))}")

assert set(ENTRY_SPECIAL_VALUES) == set(ENTRY_FIELD_LABELS), (
    "ENTRY_SPECIAL_VALUES and ENTRY_FIELD_LABELS must cover the same twelve "
    f"fields; these appear in one but not the other: "
    f"{sorted(set(ENTRY_SPECIAL_VALUES) ^ set(ENTRY_FIELD_LABELS))}")


def entry_special_values(field_name: str) -> dict:
    """
    `{value: what it means}` for the values of a column that are not ids.

    Single source of truth for both the Encounters dropdowns and their
    captions, for the same reason `entry_inherit_value` is: the control and
    the words under it cannot then disagree.

    Both tables, because a caller asking "what does 254 mean on this field"
    should not have to know whether the field is one of the twelve that
    point at rows or one of the six that hold values. The two cannot
    overlap - asserted where ENTRY_VALUE_SPECIALS is defined - so the order
    of the lookup does not matter.
    """
    return dict(ENTRY_SPECIAL_VALUES.get(field_name)
                or ENTRY_VALUE_SPECIALS.get(field_name) or {})


def entry_inherit_value(field_name: str):
    """
    The value that means "leave the game's own value alone" for a column,
    or None where the layout documents no patch condition. Single source of
    truth for both the UI's inherit labels and nxd_data's new-row defaults.
    """
    pair = ENTRY_INHERIT_VALUES.get(field_name)
    return pair[0] if pair else None


def entry_inherit_help(field_name: str) -> str:
    pair = ENTRY_INHERIT_VALUES.get(field_name)
    return pair[1] if pair else ""


def entry_new_row_value(field_name: str):
    """
    What a brand-new row should carry for a column nobody has set. The
    inherit value where one is documented, otherwise 0 - never -1, which in
    a byte column reads back as 255 and would trip any "if not zero"
    condition (see this section's header comment).
    """
    if field_name in ENTRY_ARRAY_FIELDS:
        return []
    if field_name in ENTRY_STRING_FIELDS:
        return None
    value = entry_inherit_value(field_name)
    return 0 if value is None else value

# CharaName-xx nxd table (per-language unit names) - same simple shape as
# Item-xx.
NXD_CHARANAME_TABLE = {lang: f"CharaName-{lang}" for lang in NXD_LANGUAGES}
NXD_CHARANAME_FILENAMES = {lang: f"charaname.{lang}.nxd" for lang in NXD_LANGUAGES}
NXD_OVERRIDE_ENTRY_TABLE = "OverrideEntryData"
NXD_OVERRIDE_ENTRY_FILENAME = "overrideentrydata.nxd"
NXD_ALL_ENCOUNTER_FILENAMES = list(NXD_CHARANAME_FILENAMES.values()) + [NXD_OVERRIDE_ENTRY_FILENAME]

# CharaName-xx nxd fields (per-language unit names).
CHARANAME_TEXT_FIELDS = ["Name", "Comment"]
CHARANAME_NUMERIC_FIELDS = {
    "DLCFlags": (0, 255, "DLC Flags", ""),
}
CHARANAME_BOOL_FIELDS = {
    "IsGeneric": ("Generic Unit", "Checked for generic named units, unchecked for unique named characters."),
}

# ---------------------------------------------------------------------------
# Sounds (.sab files, via AudioMog - github.com/Yoraiz0r/AudioMog, MIT) -
# see sound_data.py. Unlike Textures/nxd, there's no reference table or
# database here at all - just .sab files sitting in the unpacked game
# folder (the same one Textures already points at), each one unpacked into
# a sibling "<name>_Project/" folder by AudioMog on demand.
# ---------------------------------------------------------------------------

SOUND_EXTENSION = ".sab"
SOUND_ROOT_FRAGMENT = "sound/"
# Informational classification only (see sound_data.classify_sab_path) - the
# real "does this loop" answer comes from whether the unpacked reference
# .wav actually carries an smpl chunk, not from the path alone. These are
# just used to label a track with a plain-English expectation.
SOUND_MUSIC_PATH_FRAGMENT = "sound/music/"
SOUND_VOICE_PATH_FRAGMENT = "sound/voice/"

# =============================================================================
# Poaching - PoachItem-xx (.nxd, per-language) - see nxd_data.py.
#
# Ability 471 "Poach" lets a unit convert a monster's killing blow into an
# item instead of the normal crystal/treasure drop. Per a real poaching
# guide for this exact game, the item received is a "carcass"/"pelt" that
# gets turned in at the Poacher's Den shop (Dorter/Warjilis/Sal Ghidos) to
# unlock further items - matching the flavor text every real row here
# carries ("Used to produce a/an ...").
#
# Architecturally simpler than Ability/Item but in an unexpected way: there
# is NO separate shared numeric table (nothing like OverrideAbilityAction
# Data or ItemData.xml) - each language's PoachItem-xx table is a fully
# self-contained row, text AND numeric/economy fields together. Confirmed
# against a real fft_data.sqlite: Cost/SellPrice/IconId/IsRare/etc. matched
# across all 7 languages in every one of the 96 real rows, with exactly one
# stray exception (Unknown1E was 0 in every English row but 1 in every
# French row - see its own note below) - so, same as Item/CharaName, fields
# here are edited per-language with a "Copy to all languages" button,
# rather than forced to stay in sync.
#
# Field names below reuse the exact naming FF16Tools already gives Item-xx
# (Name/NameSingular/NamePlural/Name2/Description/Comment/DLCFlags) since
# the byte layout lines up field-for-field with it - Cost/SellPrice/
# IconId/IsRare are Poach-specific additions, and (like Item's own IconId)
# are confirmed real FF16Tools field names, not "UnknownXX" placeholders.
#
# Cross-checked directly against Zodi's real PoachItem.layout (the actual
# FF16Tools layout definition used to generate the sqlite schema, complete
# with the original reverse engineer's own disassembly notes) - every one
# of the 19 fields below (5 text + Comment + 13 numeric/bool) matches this
# layout's 19 columns exactly, in the same order, confirming full field
# coverage with nothing missed and nothing extra. It also gave real new
# leads on a few previously fully-unknown fields (Unknown1C/IsRare/
# Unknown35 - see their own notes below) - upgraded from "no leads at all"
# to "a real but sometimes ambiguous disassembly hint", not to "confirmed",
# since a hint from code that only tests one bit of a value can still
# conflict with the full range of real values actually observed - see
# Unknown35 specifically, where this tool deliberately keeps its own
# data-driven finding over the layout's own "bool" note.
# =============================================================================

# Inferred by convention (ability.<lang>.nxd / item.<lang>.nxd / charaname.
# <lang>.nxd all follow "<lowercased table name>.<lang>.nxd") - PoachItem.
# layout's own "table_name|PoachItem" line is consistent with this (lower-
# cases to "poachitem", matching the guess below) but doesn't actually
# state the on-disk .nxd filename itself, so this remains an inference,
# not yet confirmed against a real unpacked nxd/ folder. Correct this if
# Zodi's actual game folder uses a different filename.
NXD_POACH_FILENAMES = {lang: f"poachitem.{lang}.nxd" for lang in NXD_LANGUAGES}
NXD_ALL_POACH_FILENAMES = list(NXD_POACH_FILENAMES.values())


# =============================================================================
# Jobs - job.<lang>.nxd (per-language name and description)
# =============================================================================
# The OTHER Job table. `JobData.xml` (see JOB_FIELD_ORDER above) holds a
# job's stats and links and is shared across languages; this one holds the
# text the player reads, once per language. They share ZERO column names -
# `Job.layout` has Name/Description/jobtype+Id, `JOB_DATA.cs` has
# JobCommandId/HPGrowth/... - so nothing here is a duplicate of anything
# there, and neither is the schema for the other.
NXD_JOB_TABLE = {lang: f"Job-{lang}" for lang in NXD_LANGUAGES}
NXD_JOB_FILENAMES = {lang: f"job.{lang}.nxd" for lang in NXD_LANGUAGES}
NXD_ALL_JOB_FILENAMES = list(NXD_JOB_FILENAMES.values())

# What the four string columns actually are.
#
# `Unknown4` and `Unknown6` are the FEMININE forms of Name and Description.
# Confirmed from the real 1.5.1 and 1.5.2 databases, not inferred from the
# column names:
#
#   Job-de key 16  Description  "Ein hoher Geistlicher, der ... Sein ..."
#                  Unknown6     "Eine hohe Geistliche, die ... Ihr ..."
#   Job-de key 5   Name         "Heiliger Ritter"
#                  Unknown4     "Heilige Ritterin"
#
# All 45 populated German `Unknown4` values differ from `Name`; all 153
# French ones are identical to it, because French job titles here do not
# inflect but the field is filled anyway. Some rows carry a feminine
# description with no feminine name (Moench, Dragoon, Samurai, Ninja) -
# the noun does not inflect, the prose does. English, Japanese, Korean,
# Czech and Chinese leave both empty.
#
# They are LABELLED here because `is_unknown_field` judges the label, not
# the column name. Leaving them as "Unknown4"/"Unknown6" would hide two
# confirmed, translator-relevant fields behind the Hide-unknown toggle -
# the same mistake OverrideEntryData's `Unknown4` unit name once caused.
#
# `Unknown2` keeps its offset as its label. It is empty in all seven
# languages in both 1.5.1 and 1.5.2, so there is no evidence for what it
# holds, and constants.py forbids inventing a meaning.
JOB_NXD_FIELD_LABELS = {
    "Name": "Name",
    "Description": "Description",
    "Unknown4": "Name (feminine)",
    "Unknown6": "Description (feminine)",
    "Unknown2": "Unknown 2",
}

# Every string column, in the order the layout declares them.
JOB_NXD_TEXT_FIELDS = ["Name", "Unknown4", "Description", "Unknown6", "Unknown2"]

# Notes shown beside the two feminine rows, so a modder who has never seen
# a gendered string table knows what they are looking at before typing.
# Kept SHORT. These sit in the note column beside a text box, and the box is
# the part that matters - a three-sentence note on a page rendered at the
# 1100 minimum took half the row's width and pushed the five text fields
# into a column twice as tall as Basic Stats below it. The full explanation
# is in this file, above.
JOB_NXD_FIELD_NOTES = {
    "Unknown4": "Used when the unit is female.",
    "Unknown6": "The description used when the unit is female.",
    "Unknown2": "Empty in every language, so its purpose is unknown.",
}

# The numeric columns, all eleven of them. Ranges and notes come from the
# real 1.5.2 data - min/max/distinct counted per column, not guessed.
#
# The principle: if the game data has a column, this tool has somewhere to
# edit it. `dev/audit_field_coverage.py` fails when that stops being true.
JOB_NXD_NUMERIC_FIELDS = {
    "Unknown1": (0, 255),
    "jobtype+Id": (0, 255),
    "Unknown8": (0, 255),
    "jobcommand+Id": (0, 255),
    "Unknown10": (0, 255),
    "Unknown11": (0, 255),
    "TexturePartsIndex": (0, 255),
    "uijobabilityhelp+Id": (0, 255),
    "egg+Id": (0, 255),
    "Unknown15": (-1, 9999),
    "HideJobTree": (0, 1),
}

JOB_NXD_NUMERIC_LABELS = {
    "jobtype+Id": "Job Type ID",
    "jobcommand+Id": "Job Command ID (nxd copy)",
    "TexturePartsIndex": "Face Texture Parts Index",
    "uijobabilityhelp+Id": "Ability Help Text ID",
    "egg+Id": "Egg ID",
    "HideJobTree": "Hide From Job Tree",
    # The rest keep their offsets as labels - see below for what IS known
    # about them, which is not enough to name them.
}

JOB_NXD_NUMERIC_NOTES = {
    "jobtype+Id": "Links to the jobtype table. 0-114 in vanilla.",
    "jobcommand+Id": (
        "The same value as Job Command above, in the .nxd. Both are written "
        "together - see the note on that row."
    ),
    "TexturePartsIndex": (
        "Picks the face texture: "
        "ui/ffto/common/face/textureparts/wldface_<job>_<index>_uitx.utexpt"
    ),
    "uijobabilityhelp+Id": "Links to the uijobabilityhelp table. 0-34 in vanilla.",
    "egg+Id": "Links to the egg table. 0-48 in vanilla.",
    "HideJobTree": "1 hides the job from the job tree. 25 jobs use this.",
    "Unknown10": (
        "Always exactly one less than Unknown11, and only set on monster "
        "jobs (53 rows). What the pair selects is not known."
    ),
    "Unknown11": "Always Unknown10 + 1. See that row.",
    "Unknown15": (
        "Mostly multiples of ten with -1 as a sentinel, which looks like a "
        "sort order, but that is not confirmed."
    ),
    "Unknown1": "Zero on every row in every language, so nothing is known about it.",
    "Unknown8": "0-100, 24 distinct values in vanilla. Purpose unknown.",
}

# =============================================================================
# Job Commands - jobcommand.<lang>.nxd (per-language name and description)
# =============================================================================
# The OTHER Job Command table, exactly as Job has one. `JobCommandData.xml`
# holds the sixteen ability slots and six R/S/M slots; this one holds the
# name and description the player reads, once per language. Zero shared
# column names.
#
# It had NO editor at all until it was added to `nxd_data.ALL_NXD_SPECS` -
# 227 rows of names and descriptions that no mod could change, on a tab
# that already existed. `dev/audit_field_coverage.py` is what surfaces this
# kind of hole now.
NXD_JOBCOMMAND_TABLE = {lang: f"JobCommand-{lang}" for lang in NXD_LANGUAGES}
NXD_JOBCOMMAND_FILENAMES = {lang: f"jobcommand.{lang}.nxd" for lang in NXD_LANGUAGES}
NXD_ALL_JOBCOMMAND_FILENAMES = list(NXD_JOBCOMMAND_FILENAMES.values())

JOBCOMMAND_NXD_TEXT_FIELDS = ["Name", "Description", "Description2", "Comment"]

JOBCOMMAND_NXD_FIELD_LABELS = {
    "Name": "Name",
    "Description": "Description",
    "Description2": "Description (alternate)",
    "Comment": "Comment",
    "IconId": "Icon ID",
    "UiDialogId": "UI Dialog ID",
    "DLCFlags": "DLC Flags",
}

JOBCOMMAND_NXD_NUMERIC_FIELDS = {
    "DLCFlags": (0, 255),
    "IconId": (0, 255),
    "Unknown14": (0, 255),
    "Unknown1C": (0, 65535),
    "UiDialogId": (0, 255),
}

JOBCOMMAND_NXD_FIELD_NOTES = {
    "Description2": (
        "Only one row uses it in most languages."
    ),
    "IconId": "0-27 in vanilla.",
    "Unknown14": "0-226, 114 distinct values in vanilla. Purpose unknown.",
    "Unknown1C": "Only two distinct values in vanilla: 0 and 40010.",
    "UiDialogId": "0-19, only three distinct values in vanilla.",
    "DLCFlags": "0 on every row in vanilla.",
}


# --------------------------------------------------------------------------
# Fields that exist in TWO files and must be written to both.
#
# `JobData.xml`'s own header, shipped by the mod loader, says:
#
#   "This table links to nex table 'Job'. Some properties edited here may
#    be overriden by the nex table."
#
# So the .nxd WINS. A mod that sets `JobCommandId` in the XML and leaves the
# .nxd alone may find the change simply does not apply - which is a silent
# failure, because the XML is written correctly and the game ignores it.
#
# One control writes both. Two controls would let a mod disagree with
# itself with nothing to show the modder which half the game obeyed.
#
# (xml field on JobData.xml, registry key, nxd column)
LINKED_FIELDS = [
    ("JobCommandId", "job", "jobcommand+Id"),
]


# The UI string tables. Not editable anywhere in this tool - they're staged
# and converted purely because key 3737 of each holds the game's own version
# string ("v1.5.2"), which is how both an unpacked game and an opened mod
# get dated. See migration.VERSION_UI_KEY.
#
# Cheap: seven tables, well under a megabyte, against the alternative of a
# second FF16Tools invocation just to read one row. And because a mod that
# ships ui.*.nxd gets them staged too, a mod built long before Mod Studio
# existed can still say which game version it came from.
NXD_UI_TABLE = {lang: f"UI-{lang}" for lang in NXD_LANGUAGES}
NXD_UI_FILENAMES = {lang: f"ui.{lang}.nxd" for lang in NXD_LANGUAGES}
NXD_ALL_UI_FILENAMES = list(NXD_UI_FILENAMES.values())

# The .nxd files this tool actually EDITS, and therefore regenerates on
# export. Kept separate from the staged list below, which also includes the
# UI tables - those are read for their version string and never written, so
# a mod's own copies have to be carried through untouched rather than
# assumed to be regenerated. Conflating the two silently dropped every
# ui.*.nxd from any mod regenerated into a new folder.
# XML tables that have a curated tab but do NOT go through
# `item_xml_io.ALL_SPECS`. Both are handled by `xml_io` directly, because
# they were written before the generic engine existed and have controls
# (skillset dropdowns, ability pickers) a generic table editor cannot
# offer. Listed so the derived-spec loader does not offer them a second
# time as raw grids - two editors writing competing diffs for one file.
XML_HANDLED_ELSEWHERE = ("JobData.xml", "JobCommandData.xml")


NXD_EDITABLE_FILENAMES = (
    NXD_ALL_FILENAMES + NXD_ALL_ITEM_FILENAMES + NXD_ALL_ENCOUNTER_FILENAMES
    + NXD_ALL_POACH_FILENAMES + NXD_ALL_JOB_FILENAMES
    + NXD_ALL_JOBCOMMAND_FILENAMES
)

# Every .nxd this tool stages for conversion, in one place so callers can't
# drift from it - step_setup used to add the four lists up by hand to report
# "found N of M", which silently under-counted the moment a list was added.
NXD_ALL_STAGED_FILENAMES = NXD_EDITABLE_FILENAMES + NXD_ALL_UI_FILENAMES

# SQLite table names FF16Tools produces (verified against the real
# fft_data.sqlite Zodi uploaded for this feature).
NXD_POACH_TABLE = {lang: f"PoachItem-{lang}" for lang in NXD_LANGUAGES}

POACH_TEXT_FIELDS = ["Name", "NameSingular", "NamePlural", "Name2", "Description", "Comment"]

POACH_NUMERIC_FIELDS = {
    # name: (min, max, label, help text)
    "DLCFlags": (0, 255, "DLC Flags", ""),
    # Cost, Sell Price and Produces / Unlocks Item carry no note, at Zodi's
    # request. What Produces' note said - that the field's meaning is
    # INFERRED (FF16Tools calls it Unknown2C; its value matches the
    # carcass's own flavour text on 95 of 96 real rows, e.g. Chocobo Carcass
    # -> 253 Phoenix Down) - is recorded here rather than lost, and HANDOFF
    # says so.
    "Cost": (0, 65535, "Cost", ""),
    "SellPrice": (0, 65535, "Sell Price", ""),
    "IconId": (0, 65535, "Icon ID",
               "References the position on the ui_poachers_den_monster_icon_uitx texture."),
    "ProducedItemId": (0, MAX_ITEM_ID, "Produces / Unlocks Item", ""),
    # Unknown1C, 1E, 20 and 35: shortened to at most 150 characters, with a
    # hyphen only between two numbers - Zodi's two rules, checked by
    # `test_qt_poaching` with len() and a regex rather than by eye. Written
    # from the rows, not from the old notes: measured on 1.4.0, 1.5.1 and
    # 1.5.2, the old 1C note ("0 in every real row checked") was wrong - 8
    # English rows hold 1, exactly the carcasses whose English name starts
    # with a vowel. The same suite checks every fact below against the data.
    "Unknown1C": (0, 255, "Unknown1C",
                  '1 on the 8 English rows whose name starts with a vowel, 0 '
                  'on every other row. Inferred: whether English says "an" '
                  'rather than "a".'),
    "Unknown1D": (0, 255, "Unknown1D", "1 in every real row checked."),
    "Unknown1E": (0, 255, "Unknown1E",
                  '1 on every French row, 0 in every other language. Every '
                  'French name starts "Carcasse", so perhaps grammatical '
                  'gender. Not confirmed.'),
    "Unknown1F": (0, 255, "Unknown1F", "0 in every real row checked."),
    "Unknown20": (0, 2147483647, "Unknown20",
                  "0 in every real row checked. A four byte integer in "
                  "PoachItem.layout, not one byte like 1C to 1F, so the box "
                  "allows the full range."),
    "Unknown35": (0, 255, "Unknown35",
                  "A second index in Key order: common carcasses run 1-48, "
                  "rare ones 51-98. The layout calls it a bool; the data "
                  "does not, so it stays a number."),
    "Unknown36": (0, 255, "Unknown36", (
        "0 in all but 3 of the 96 real rows checked (Dryad Carcass<Icon=103>, Behemoth King "
        "Carcass<Icon=103>, Hydra Carcass) - meaning unknown."
    )),
}

POACH_BOOL_FIELDS = {
    # Shortened at Zodi's request (150 characters at most, no "-" outside
    # a number range). What the long version carried, so it is not lost:
    # the flag matches the "<Icon=103>" marker in the carcass's name on all
    # 96 real rows, 48 each way; and PoachItem.layout says "used for icon.
    # IconId = 503 + this" - a hardcoded icon computed from this byte,
    # separate from the Icon ID column.
    "IsRare": ("Rare Variant", (
        "Checked for a monster's rare carcass, unchecked for its common one. "
        "The game also picks a separate icon from it: 503 if common, 504 if rare."
    )),
}

# Friendly field name -> actual sqlite column name. Unlike Ability-xx/
# Item-xx (whose real columns already ARE "Name"/"Description"/etc.),
# PoachItem-xx's real columns are FF16Tools' raw "UnknownXX" hex-offset
# names for the fields inferred above (see the field notes above for the
# evidence) - this is where that translation happens, once, right at the
# nxd_data.py read/write boundary, same idea as split_jp_cost/join_jp_cost
# translating Ability's JpCost. Every field NOT listed here already has a
# real/matching column name (DLCFlags, Comment, Cost, SellPrice, IconId,
# IsRare, Unknown1C/1D/1E/1F/20/35/36) and passes through unchanged.
POACH_FIELD_RAW_NAMES = {
    "Name": "Unknown8",
    "NameSingular": "UnknownC",
    "NamePlural": "Unknown10",
    "Name2": "Unknown14",
    "Description": "Unknown18",
    "ProducedItemId": "Unknown2C",
}
POACH_FIELD_FRIENDLY_NAMES = {raw: friendly for friendly, raw in POACH_FIELD_RAW_NAMES.items()}

# =============================================================================
# Treasure Hunter - MapTrapFormationData.xml (buried-treasure / "Move-Find
# Item" tiles) - a single reference/diff XML table, the exact same shape as
# the six Item*Data.xml tables, so it's wired into item_xml_io.py's generic
# TableSpec engine (MAP_TRAP_SPEC) rather than needing its own read/write code.
#
# Ability 509 "Treasure Hunter" (vanilla FFT/FFTPatcher call this "Move-Find
# Item") lets a unit dig up buried treasure on specially-marked tiles. Each
# map can have up to 4 such tiles ("Tile 1".."Tile 4" in the interface); walking a
# Treasure-Hunter-equipped unit onto one gives either its Rare or Common
# item. Per FFHacktics' research into the original game's formula, lower
# Brave means better odds of the Rare item - see https://ffhacktics.com/
# wiki/Move_find_item_flag_calculation (a PSX-era reverse-engineering
# source; unconfirmed whether Ivalice Chronicles kept that exact formula).
#
# Everything below is now confirmed directly from the real mod loader
# source (Zodi's own FFTOMapTrapFormationDataManager.cs), not just cross-
# referenced indirectly:
# - Filename: `TableFileName => "MapTrapFormationData"`, and RegisterFolder
#   reads "{TableFileName}.xml" - i.e. literally MapTrapFormationData.xml,
#   confirming (not just corroborating) the same conclusion this tool
#   already reached by cross-referencing a real published Nexus mod ("Only
#   Rare Treasure") - takes precedence over the stale "MapTrapData.xml"
#   name mentioned in the shipped file's own header comment (an old/
#   internal name, not what the mod loader itself actually looks for).
# - Table size: `NumEntries => 128`, `MaxId => NumEntries - 1` (127) -
#   confirms MAX_MAPTRAP_ID below exactly.
# - X/Y really are packed into one nibble each in memory
#   (`XY1 = (X1 & 0x0F) << 4 | (Y1 & 0x0F)`, confirming 0-15 is the real
#   valid range for MAPTRAP_XY_MIN/MAX below) - but the packing only
#   happens at that final memory-patch step; the diff-XML model this tool
#   reads/writes still exposes X1/Y1 as two separate nullable fields
#   (`mapItem.X1`/`mapItem.Y1`), exactly like the real XML sample already
#   showed, so nothing about this tool's own field handling needed to
#   change.
# - The trap-flags field is a real `[Flags]`-style enum in the game's own
#   code, typed `MapItemTrapFlags` - confirms this is a real enum, not
#   just several loose bits this tool happened to group together.
# - RareItemId/CommonItemId are cast to `ushort` (0-65535) on write -
#   consistent with holding an ordinary ItemData id.
# - Confirms the diff/inherit semantics this tool already assumes: a null/
#   unset field falls back to `previous` (whatever the mod load order
#   already established, not necessarily vanilla) - the same "only
#   explicitly-included fields are written" rule as every other diff table
#   here.
#
# One more stale detail in the shipped file's own header comment (kept
# verbatim in item_xml_io.py's _MAP_TRAP_HEADER regardless, matching every
# other table's header here, since generated diffs should look like a
# hand-edited copy of the real file): it points modders to a
# "MAP_ITEM_DATA.cs" struct reference for the trap flag values, but the
# real manager class (FFTOMapTrapFormationDataManager.cs) references its
# own struct as MAP_TRAP_FORMATION_DATA - so that particular link in the
# generated file is likely just as stale as the "MapTrapData.xml" name
# right above it in the same comment block.
# =============================================================================

MAX_MAPTRAP_ID = 127   # hardcoded table size is 128 (0-127) - Id 0 is an empty/dummy slot
MAPTRAP_SLOTS = [1, 2, 3, 4]     # up to 4 treasure tiles per map
MAPTRAP_XY_MIN, MAPTRAP_XY_MAX = 0, 15   # each map's grid is 16x16

# TrapFlags# - a real [Flags] enum in the game's own code (typed
# `MapItemTrapFlags`, confirmed via FFTOMapTrapFormationDataManager.cs -
# see above), comma-combinable (e.g. "Degenerator, Deathtrap"), same
# parse_flag_value/format_flag_value convention as ItemTypeFlags etc.
# "None" (the implicit empty selection) = a plain treasure tile with no
# trap. The five members below are real values confirmed in Zodi's own
# real MapTrapFormationData.xml, both alone and combined - the enum's own
# full member list (i.e. whether more exist beyond what's actually used in
# the shipped data) hasn't been seen directly.
# AlwaysTrap and NoActivation come from the mod loader's MapItemTrapFlags
# enum via dev/audit_flag_enums.py; no vanilla row uses either. Its `Unused1`
# padding member is deliberately left out and stays INFO in the audit.
MAPTRAP_TRAP_FLAGS = ["DisableTrap", "Deathtrap", "Degenerator", "SleepingGas", "SteelNeedle",
                      "AlwaysTrap", "NoActivation"]

# One entry per logical field (base name, without the 1-4 slot suffix) -
# the GUI builds 4 near-identical rows (Item 1..Item 4) from this.
MAPTRAP_SLOT_FIELD_LABELS = {
    "X": "X",
    "Y": "Y",
    "TrapFlags": "Trap",
    "RareItemId": "Rare Item",
    "CommonItemId": "Common Item",
}

MAPTRAP_FIELD_ORDER = [
    f"{base}{slot}"
    for slot in MAPTRAP_SLOTS
    for base in ("X", "Y", "TrapFlags", "RareItemId", "CommonItemId")
]

# =============================================================================
# Ability Effect - AbilityEffectNumberFilterData.xml (determines which
# hardcoded "effect" - see https://ffhacktics.com/wiki/Effects - an ability
# triggers when it executes). Same id space as AbilityData.xml/Ability-xx
# (0-453), so this lives as its own sub-tab inside the Abilities tab itself,
# right next to Flags/Element/Overrides - but it's an ordinary reference/
# diff XML table, not OverrideAbilityActionData, so it's wired into
# item_xml_io.py's generic TableSpec engine exactly like Treasure Hunter's
# MapTrapFormationData.xml above, rather than a second near-duplicate
# per-ability sub-tab engine. No game unpack/nxd conversion needed for this
# one specifically (unlike Ability Info/Flags/Element/Overrides, which all
# require a converted ability database) - but it still lives behind the same
# ability-picker tree as those, which does require one; see step_abilities.py.
#
# Confirmed directly from Zodi's real FFTOAbilityEffectNumberFilterDataManager.cs:
# - Filename: TableFileName => "AbilityEffectNumberFilterData" (RegisterFolder
#   reads "{TableFileName}.xml") - i.e. literally AbilityEffectNumberFilterData.xml.
#   The shipped file's own header comment tells modders to copy their file to
#   "AbilityEffectData.xml" instead - a stale name, same story as
#   MapTrapFormationData.xml's own header pointing at "MapTrapData.xml" above;
#   kept verbatim in item_xml_io.py's own header constant regardless (so a
#   generated diff still reads like a hand-edited copy of the real file), but
#   TABLE_FILENAMES above uses the real, manager-confirmed name.
# - Table size: NumEntries => 454, MaxId => 453 - same id space as AbilityData.
# - EffectId is cast to `short` (a real signed 16-bit field, not ushort) -
#   confirms negative values are legitimate, not a parsing artifact. Real
#   shipped data uses -1 for 64 abilities, including all four "Rend"/Break
#   skills (Rend Helm/Armor/Shield/Weapon/MP) - apparently "no separate effect
#   entry, just the hardcoded break logic" rather than a placeholder; positive
#   values observed up to 2333. Bounds below use the type's full signed
#   range, same convention as every other cast-native-type field in this tool
#   (e.g. ABILITY_NUMERIC_FIELDS["DLCFlags"] uses the full int32 range rather
#   than just what's observed in the shipped data).
# =============================================================================
MAX_ABILITY_EFFECT_ID = 453   # hardcoded table size is 454 (0-453) - same ids as AbilityData
ABILITY_EFFECT_ID_MIN, ABILITY_EFFECT_ID_MAX = -32768, 32767   # signed short, confirmed via real manager cast
ABILITY_EFFECT_FIELD_ORDER = ["EffectId"]

# =============================================================================
# Unit Animations - AbilityTypeData.xml (determines which animation(s) play
# when an ability executes - https://ffhacktics.com/wiki/Animations_(Tab)).
# Same story as Ability Effect directly above: its own Abilities sub-tab,
# item_xml_io.py TableSpec, same id space (0-453) as AbilityData.xml.
#
# Confirmed directly from Zodi's real FFTOAbilityTypeDataManager.cs:
# - Filename: TableFileName => "AbilityTypeData" (matches the shipped file's
#   own header comment - no stale-name issue here, unlike Ability Effect
#   above and Treasure Hunter's MapTrapFormationData.xml).
# - Table size: NumEntries => 454, MaxId => 453 - same id space as AbilityData.
# - All three fields (ChargeEffectType, AnimationId, BattleTextId) are cast
#   to `byte` on write - confirms 0-255 as the real field type. Real shipped
#   data observed within 0-18 / 0-125 / 0-47 respectively, well inside that
#   range - bounds below use the full byte range regardless, same convention
#   as everywhere else in this tool.
# =============================================================================
MAX_ABILITY_ANIMATION_ID = 453   # hardcoded table size is 454 (0-453) - same ids as AbilityData
ABILITY_ANIMATION_FIELD_ORDER = ["ChargeEffectType", "AnimationId", "BattleTextId"]

# =============================================================================
# Ability's own base-stat table - AbilityData.xml itself (not to be confused
# with Ability Effect/Unit Animations above, which are separate tables that
# merely SHARE AbilityData's id space). Same story as those two: an ordinary
# reference/diff XML table, wired into item_xml_io.py's generic TableSpec
# engine, living as its own Abilities sub-tab rather than a top-level tab
# since it's keyed by the same ability id as everything else there.
#
# Confirmed field-for-field against Zodi's real uploaded Ability.cs
# (fftivc.utility.modloader.Interfaces.Tables.Models.Ability, the actual mod
# loader model class) - JPCost, ChanceToLearn, Flags, AbilityType,
# AIBehaviorFlags is that class's exact PropertyMap, in the exact order
# declared there. The bundled data/AbilityData.xml (byte-identical, aside
# from line endings, to Zodi's own upload) confirms every field's real
# string values across all 512 rows.
#
# JPCost is intentionally NOT exposed as an editable field here. The shipped
# file's own header comment says so explicitly, on the very first entry:
# "NOTE! Only JPCost from the Ability nex table is used. This one is
# unused!" - that nex-table JPCost is already the one this tool edits on the
# Ability Info tab (nxd, Ability-xx/JpCostRow). Exposing a second, dead
# JPCost field here would look editable while doing nothing in-game - same
# "don't expose a field with no honest effect" principle already applied to
# the nxd side's excluded UnknownXX fields.
#
# Flags and AIBehaviorFlags are both real [Flags]-style enums - the exact
# same plain comma-separated convention as ItemTypeFlags/MapTrapTrapFlags,
# handled by the same generic parse_flag_value/format_flag_value engine, no
# bit-packing math needed on this tool's side (the shipped file's own string
# values ARE the full field). This is a genuinely different flag system from
# the binary-packed "Ability Flags I-IV" on the Flags/Element/Overrides
# sub-tab (those come from the nxd OverrideAbilityActionData table instead)
# - two unrelated systems that happen to both be called "flags".
#
# Canonical orderings below list every value actually observed across all
# 512 real rows in the bundled AbilityData.xml - not a full source-confirmed
# enum member list. Per Ability.cs's own bit-shift ((flags >> 4) & 0b1111),
# Flags is a 4-bit field (up to 16 possible values), but only 3 named values
# ever appear in the real shipped data - any further bit position(s), if
# they exist, have no confirmed name and aren't offered as a checkbox here,
# matching this project's existing "blank"/unused-slot convention (Ability
# Flags I-IV's own blank7).
# =============================================================================
ABILITY_XML_FLAGS = ["DisplayAbilityName", "DontLearnWithJP", "LearnOnHit"]

# AI targeting/behavior flags - all 27 real values observed across every row.
# Individual flag semantics are inferred from their own names only (not
# independently confirmed against a source comment or struct); grouped below
# purely for on-screen readability, not asserting a deeper confirmed
# structure.
ABILITY_AI_BEHAVIOR_FLAGS = [
    "TargetEnemies", "TargetAllies", "TargetMap", "OnlyHitsEnemies", "OnlyHitsAlliesOrSelf",
    "HP", "MP", "Stats",
    "AddStatus", "CancelStatus", "UndeadReverse", "AffectedByFaith", "Silence",
    "PhysicalAttack", "MagicalAttack", "LinearAttack", "Ranged3Directions",
    "Melee3Directions", "NonSpearAttack", "RandomHits", "StopAtObstacle",
    "Evadeable", "EvadeWithMotion", "Reflectable", "Unequip", "CheckCT_Target", "UsableByAI",
    # Added after dev/audit_flag_enums.py found them in the mod loader's own
    # AIBehaviorFlags enum and absent here. No vanilla row uses any of the
    # three, so nothing was being dropped - a modder simply could not set
    # them. The enum's padding members (Unk_25, Unk_28) are deliberately
    # still absent; the audit reports those as INFO, not GAP.
    "Arced", "UseWeaponRange", "RequireMonsterSkill",
]
ABILITY_AI_BEHAVIOR_GROUPS = {
    "Targeting": ["TargetEnemies", "TargetAllies", "TargetMap", "OnlyHitsEnemies", "OnlyHitsAlliesOrSelf"],
    "Resource Type": ["HP", "MP", "Stats"],
    "Status": ["AddStatus", "CancelStatus", "UndeadReverse", "AffectedByFaith", "Silence"],
    "Attack Pattern": [
        "PhysicalAttack", "MagicalAttack", "LinearAttack", "Ranged3Directions",
        "Melee3Directions", "NonSpearAttack", "RandomHits", "StopAtObstacle",
    ],
    "Special": ["Evadeable", "EvadeWithMotion", "Reflectable", "Unequip", "CheckCT_Target", "UsableByAI"],
    "Targeting Rules": ["Arced", "UseWeaponRange", "RequireMonsterSkill"],
}
assert set(ABILITY_AI_BEHAVIOR_FLAGS) == {f for flags in ABILITY_AI_BEHAVIOR_GROUPS.values() for f in flags}

# AbilityType - single-select (not a [Flags] field). All 10 real values
# observed across every row - matches ACTION_ABILITY_TYPES/RSM_ABILITY_TYPES
# above (this is in fact their original source) plus "None".
ABILITY_TYPE_XML_VALUES = [
    "None", "Normal", "Item", "Throwing", "Jumping", "Aim", "Math", "Reaction", "Support", "Movement",
]
assert set(ABILITY_TYPE_XML_VALUES) == ({"None"} | ACTION_ABILITY_TYPES | RSM_ABILITY_TYPES)

ABILITY_XML_NUMERIC_FIELDS = {
    # ChanceToLearn is a byte per Ability.cs - full native range shown even
    # though every real row is 0-100.
    "ChanceToLearn": (
        0, 255, "Chance to Learn",
        "Percent chance to learn this ability on a successful hit, for jobs/abilities that grant "
        "random-chance learning. Real shipped data is always 0-100.",
    ),
}

ABILITY_XML_FIELD_ORDER = ["ChanceToLearn", "Flags", "AbilityType", "AIBehaviorFlags"]

# ---------------------------------------------------------------------------
# Edited-row highlight
# ---------------------------------------------------------------------------
# Edited rows used to be marked with green *text*, which is hard to pick out
# against the tree background at a glance - the whole point of the marker is
# to answer "what did I change?" without reading every row. A filled row
# reads instantly; the dark green text on a pale green fill keeps contrast
# well above what light-on-light text managed.
EDITED_ROW_BG = "#c7ecc9"
EDITED_ROW_FG = "#14532d"
