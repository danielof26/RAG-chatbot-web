from datetime import datetime


def isoformat_fields(doc: dict, fields) -> dict:
    """Converts the given datetime fields of a document to ISO strings, in place."""
    for field in fields:
        if field in doc and isinstance(doc[field], datetime):
            doc[field] = doc[field].isoformat()
    return doc


def serialize_doc(doc: dict, date_fields=('created_at',)) -> dict:
    """Makes a MongoDB document JSON-serializable: _id as string and the given datetime fields as ISO."""
    doc['_id'] = str(doc['_id'])
    return isoformat_fields(doc, date_fields)
