import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = (
    os.getenv("MONGODB_URI")
    or os.getenv("MONGO_URI")
    or os.getenv("MONGO_DETAILS")
    or "mongodb://localhost:27017"
)

DB_NAME = os.getenv("MONGO_DB") or "loan_processing"

is_atlas = "mongodb+srv" in MONGODB_URI or "ssl=true" in MONGODB_URI.lower()
client_kwargs = {"serverSelectionTimeoutMS": 5000}
if is_atlas:
    client_kwargs["tls"] = True
    client_kwargs["tlsAllowInvalidCertificates"] = True

client = MongoClient(MONGODB_URI, **client_kwargs)
database = client[DB_NAME]
applications = database["loan_applications"]


def get_application(application_id: str) -> dict | None:
    """
    Retrieve one loan application from MongoDB.

    Parameters:
        application_id: MongoDB _id of the application.

    Returns:
        The application document as a Python dictionary,
        or None if the application does not exist.
    """
    return applications.find_one({"_id": application_id})


def get_all_applications() -> list[dict]:
    """
    Retrieve all loan application documents from MongoDB.

    Returns:
        List of application documents.
    """
    return list(applications.find())


def update_comparison_result(
    application_id: str,
    comparison_result: dict,
) -> None:
    """
    Store the comparison result inside the application document.
    """
    applications.update_one(
        {"_id": application_id},
        {
            "$set": {
                "comparison_status": "COMPLETED",
                "comparison_result": comparison_result,
            }
        },
    )
