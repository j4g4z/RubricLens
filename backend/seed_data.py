"""Demo rubric loader for the CM2020 final assessment rubric."""

import json
import os
from backend.database import create_rubric, add_criterion

SAMPLE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data")


def load_demo_rubric(db_path=None) -> int:
    """Load the CM2020 demo rubric from JSON into the database.

    Returns the rubric_id of the created rubric.
    """
    json_path = os.path.join(SAMPLE_DATA_DIR, "cm2020_rubric.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rubric_id = create_rubric(data["title"], data["total_marks"], db_path=db_path)

    for i, criterion in enumerate(data["criteria"]):
        descriptors = [
            {"level": d["level"], "text": d["text"]}
            for d in criterion.get("descriptors", [])
        ]
        add_criterion(
            rubric_id,
            criterion["name"],
            criterion["max_marks"],
            order_index=i,
            descriptors=descriptors,
            db_path=db_path,
        )

    return rubric_id


def load_rubric_from_json(json_data: dict, db_path=None) -> int:
    """Load a rubric from a JSON dict into the database.

    Expected format matches cm2020_rubric.json structure.
    Returns the rubric_id.
    """
    rubric_id = create_rubric(
        json_data["title"],
        json_data.get("total_marks", 0),
        db_path=db_path,
    )

    for i, criterion in enumerate(json_data.get("criteria", [])):
        descriptors = [
            {"level": d["level"], "text": d["text"]}
            for d in criterion.get("descriptors", [])
        ]
        add_criterion(
            rubric_id,
            criterion["name"],
            criterion.get("max_marks", 0),
            order_index=i,
            descriptors=descriptors,
            db_path=db_path,
        )

    return rubric_id
