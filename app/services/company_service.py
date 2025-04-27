from supabase import Client


async def get_company_id(
    supabase: Client,
    company_name: str,
):
    """
    Get the company ID from the database based on the company name.
    """
    try:
        response = (
            supabase.table("company_client")
            .select("company_id")
            .eq("name", company_name)
            .execute()
        )
        if not response.data:
            raise ValueError("Company not found")
        return response.data[0]["company_id"]
    except Exception as e:
        raise e
