import re


def safe_photo_name(text, max_length=72):
    value = str(text or "").strip()
    value = re.sub(r'[\\/:*?"<>|]', "_", value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._ ")
    return (value or "미지정")[:max_length]


def equipment_folder_name(target, slot, equipment_index):
    equipment = safe_photo_name(
        target.get("설비종류", slot.get("설비종류", "장비"))
    )
    inspection_no = safe_photo_name(
        target.get("점검번호", "") or str(equipment_index)
    )
    management_no = safe_photo_name(
        target.get("관리번호", "") or "관리번호미지정"
    )
    return (
        f"{equipment_index:02d}_{equipment}"
        f"_점검{inspection_no}_{management_no}"
    )


def photo_file_stem(slot_index, slot):
    label = safe_photo_name(slot.get("촬영항목", "사진"))
    return f"{slot_index:02d}_{label}"
