import os
import csv
import json
import math
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)


# Initialize client with your API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_keywords_volumes_from_csv(csv_path):

    # Read CSV
    with open(csv_path, newline='', encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        rows = list(reader)

    # Convert Search Volume to integers
    for row in rows:
        try:
            row["Search Volume"] = int(row["Search Volume"])
        except (ValueError, TypeError):
            row["Search Volume"] = 0

    # Sort by Search Volume
    rows_sorted = sorted(rows, key=lambda x: x["Search Volume"], reverse=True)

    # Take top 10 or fewer if not enough
    top_rows = rows_sorted[:min(10, len(rows_sorted))]

    # Create string of keyword + volume lines
    keywords_with_volumes_str = "\n".join(
        f"{row['Keyword Phrase']} {row['Search Volume']}"
        for row in top_rows
    )

    # Create array of volumes
    volumes_array = [row["Search Volume"] for row in top_rows]

    print(volumes_array)
    keywords_with_volumes_str += "Aforementioned are the top keywords sorted by search volume."
    return keywords_with_volumes_str, volumes_array

def get_gpt_response(user_content, search_volumes):
    try:
        response = client.chat.completions.create(
            model="gpt-4",  # or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": """
                    You are an expert Amazon market analyzer assistant. 
                    You will be given a list of top keywords sorted by search volume. 
                    You are to analyze the current market situation and return the following estimated average values for the product in JSON format 
                    like this: {"CTR": 0.01, "CVR": 0.02, "AOV": 100, "COGS": 50, "Fees": 10, "PPC": 10}  where the values are in the same currency as the AOV: 
                    CTR: Click-Through Rate based on the expected search rank for those keywords.
                    CVR: Conversion Rate for the product listing.
                    AOV: Average Order Value, also known as the selling price.
                    COGS: Cost of Goods Sold per unit.
                    Fees: Amazon Fees (Referral + FBA) per unit.
                    PPC: Advertising Spend (PPC) per unit required to achieve the rank/traffic.
                    DO NOT include any other text or comments in your response, only the JSON object.
                """},
                {"role": "user", "content": user_content}
            ]
        )
        content = response.choices[0].message.content
        print(content)

        # Strip leading/trailing whitespace
        content_stripped = content.strip()

        try:
            # Try to load content as JSON dictionary
            content_dict = json.loads(content_stripped)
            # print(content_dict)
            #use search_volumes and content_dict to calculate the following:
            # Traffic = Volume × CTR
            #     * Sales = Traffic × CVR
            #     * Revenue = Sales × AOV
            #     * Profit per Unit = AOV – (COGS + Fees + Ads)
            #     * Total Profit = Sales × Profit per Unit
            traffic_ranks = [volume * content_dict["CTR"] for volume in search_volumes]
            sales = [traffic_rank * content_dict["CVR"] for traffic_rank in traffic_ranks]
            revenue = [sale * content_dict["AOV"] for sale in sales]
            # profit_per_unit = [content_dict["AOV"] - (content_dict["COGS"] + content_dict["Fees"] + content_dict["PPC"])]
            # total_profit = [sale * profit_per_unit for sale in sales]
            #calculate profit per unit start ads and profit per unit end ads separately , they cant be the same
            profit_per_unit_start_ads = content_dict["AOV"] - (content_dict["COGS"] + content_dict["Fees"] + content_dict["PPC"])
            profit_per_unit_end_ads = content_dict["AOV"] - (content_dict["COGS"] + content_dict["Fees"])
            total_profit_start_ads = [sale * profit_per_unit_start_ads for sale in sales]
            total_profit_end_ads = [sale * profit_per_unit_end_ads for sale in sales]

            # print(f"Traffic Ranks: {traffic_ranks}")
            # print(f"Sales: {sales}")
            # print(f"Revenue: {revenue}")
            # print(f"Total Profit Start Ads: {total_profit_start_ads}")
            # print(f"Total Profit End Ads: {total_profit_end_ads}")

            low_traffic = [vol * 0.875 * content_dict["CTR"] for vol in search_volumes]
            low_sales = [traffic_rank * 0.75 * content_dict["CVR"] for traffic_rank in low_traffic]
            low_revenue = [sale * profit_per_unit_start_ads for sale in low_sales]

            high_traffic = [vol * 1.125 * content_dict["CTR"] for vol in search_volumes]
            high_sales = [traffic_rank * 1.25 * content_dict["CVR"] for traffic_rank in high_traffic]
            high_revenue = [sale * profit_per_unit_start_ads for sale in high_sales]
            
            base_total_sales = math.floor(sum(sales))
            base_total_revenue = round(sum(revenue), 2)
            base_total_profit_start_ads = round(sum(total_profit_start_ads), 2)
            base_total_profit_end_ads = round(sum(total_profit_end_ads), 2)

            low_total_sales = math.floor(sum(low_sales))
            low_total_revenue = round(sum([sale * content_dict["AOV"] for sale in low_sales]), 2)
            low_total_profit = round(sum(low_revenue), 2)

            high_total_sales = math.floor(sum(high_sales))
            high_total_revenue = round(sum([sale * content_dict["AOV"] for sale in high_sales]), 2)
            high_total_profit = round(sum(high_revenue), 2)

            # print(f"Base Total Sales: {base_total_sales} units")
            # print(f"Base Total Revenue: {base_total_revenue}")
            # print(f"Base Total Profit Start Ads: {base_total_profit_start_ads}")
            # print(f"Base Total Profit End Ads: {base_total_profit_end_ads}")
            # print("-----------------------------------------")
            # print(f"Low Total Sales: {low_total_sales} units")
            # print(f"Low Total Revenue: {low_total_revenue}")
            # print(f"Low Total Profit: {low_total_profit}")
            # print("-----------------------------------------")
            # print(f"High Total Sales: {high_total_sales} units")
            # print(f"High Total Revenue: {high_total_revenue}")
            # print(f"High Total Profit: {high_total_profit}")

            return {
                "base_total_sales": base_total_sales,
                "base_total_revenue": base_total_revenue,
                "base_total_profit_start_ads": base_total_profit_start_ads,
                "base_total_profit_end_ads": base_total_profit_end_ads,
                "low_total_sales": low_total_sales,
                "low_total_revenue": low_total_revenue,
                "low_total_profit": low_total_profit,
                "high_total_sales": high_total_sales,
                "high_total_revenue": high_total_revenue,
                "high_total_profit": high_total_profit,
            }

        except json.JSONDecodeError:
            
            print("Error: Response is not a valid JSON dictionary.")
            return {"Error": "Response is not a valid JSON dictionary."}

    except Exception as e:
        print(f"Error during API call: {e}")
        return {"Error": f"Error during API call: {e}"}

