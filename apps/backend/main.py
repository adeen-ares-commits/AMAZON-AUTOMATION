from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import subprocess
import json
import os
import sys
import pandas as pd
import tempfile

# from manual import process_manual_csv
from pathlib import Path


# Import scraper functions directly from current directory
from main_loop import run_scraper_main, is_scraper_running, add_to_queue

app = FastAPI(title="Amazon Automation API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class Product(BaseModel):
    productname: str
    url: str
    keyword: str
    categoryUrl: str
    csvFile: Optional[str] = None  # File name reference

class Country(BaseModel):
    name: str
    products: List[Product]

class Brand(BaseModel):
    brand: str
    countries: List[Country]

class SubmissionRequest(BaseModel):
    brands: List[Brand]

class SubmissionResponse(BaseModel):
    ok: bool
    message: str
    payload: dict

VALID_COUNTRIES = ["US", "UK", "CAN", "AUS", "DE", "UAE"]

def normalize_country(country_name: str) -> str:
    """Normalize country name to standard format"""
    country = country_name.strip().upper()
    if country == "AU":
        return "AUS"
    return country

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"ok": True}

@app.get("/api/scraper-status")
async def get_scraper_status():
    """Get current scraper status"""
    from main_loop import get_queue
    queue_items = get_queue()
    return {
        "running": is_scraper_running(),
        "queue_size": len(queue_items)
    }

@app.post("/api/submissions", response_model=SubmissionResponse)
async def create_submission(request: SubmissionRequest):
    """Create a new submission and start the scraper"""
    try:
        # Validate input
        if not request.brands:
            raise HTTPException(status_code=400, detail="No brands provided")

        # Prepare payload for scraper
        scraper_payload = {
            "brands": []
        }

        for brand in request.brands:
            # Filter valid countries
            valid_countries = []
            for country in brand.countries:
                normalized_country = normalize_country(country.name)
                if normalized_country in VALID_COUNTRIES:
                    valid_countries.append({
                        "name": normalized_country,
                        "products": [
                            {
                                "productname": product.productname,
                                "url": product.url,
                                "keyword": product.keyword,
                                "categoryUrl": product.categoryUrl
                            }
                            for product in country.products
                        ]
                    })

            if valid_countries:
                scraper_payload["brands"].append({
                    "brand": brand.brand,
                    "countries": valid_countries
                })

        if not scraper_payload["brands"]:
            raise HTTPException(status_code=400, detail="No valid countries found")

        print("Prepared scraper payload:", json.dumps(scraper_payload, indent=2))

        # Check if scraper is already running
        if is_scraper_running():
            print("Scraper is currently running, adding to queue")
            
            # Add to queue
            if add_to_queue(scraper_payload):
                return SubmissionResponse(
                    ok=True,
                    message="Data submitted to queue, will start processing once scraper is free",
                    payload=scraper_payload
                )
            else:
                raise HTTPException(status_code=500, detail="Failed to add to queue")
        else:
            # Start scraper in background
            import threading
            
            def run_scraper_background():
                try:
                    print("Starting scraper in background...")
                    result = run_scraper_main(scraper_payload)
                    print("Scraper completed:", result)
                except Exception as e:
                    print(f"Scraper error: {e}")

            # Start scraper in background thread
            scraper_thread = threading.Thread(target=run_scraper_background)
            scraper_thread.daemon = True
            scraper_thread.start()

            print("Scraper started successfully in background")
            
            return SubmissionResponse(
                ok=True,
                message="Scraper started successfully in the background",
                payload=scraper_payload
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Submission processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Submission processing failed: {str(e)}")

@app.post("/api/submissions-with-files", response_model=SubmissionResponse)
async def create_submission_with_files(
    brands_data: str = Form(...),  # JSON string of brands data
    csv_files: List[UploadFile] = File(...)
):
    """Create a new submission with CSV files and start the scraper"""
    try:
        # Parse the brands data
        try:
            brands_json = json.loads(brands_data)
            request = SubmissionRequest(**brands_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in brands_data")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid brands data: {str(e)}")

        # Validate input
        if not request.brands:
            raise HTTPException(status_code=400, detail="No brands provided")

        # Create a mapping of CSV files by their names and save them temporarily
        csv_files_map = {}
        temp_files = []
        
        for file in csv_files:
            # Save the uploaded file to a temporary location
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
            content = await file.read()
            temp_file.write(content)
            temp_file.close()
            
            csv_files_map[file.filename] = temp_file.name
            temp_files.append(temp_file.name)

        # Prepare payload for scraper
        scraper_payload = {
            "brands": []
        }

        for brand in request.brands:
            # Filter valid countries
            valid_countries = []
            for country in brand.countries:
                normalized_country = normalize_country(country.name)
                if normalized_country in VALID_COUNTRIES:
                    valid_countries.append({
                        "name": normalized_country,
                        "products": [
                            {
                                "productname": product.productname,
                                "url": product.url,
                                "keyword": product.keyword,
                                "categoryUrl": product.categoryUrl,
                                "csvFile": product.csvFile,
                                "csvFilePath": csv_files_map.get(product.csvFile) if product.csvFile else None
                            }
                            for product in country.products
                        ]
                    })

            if valid_countries:
                scraper_payload["brands"].append({
                    "brand": brand.brand,
                    "countries": valid_countries
                })

        if not scraper_payload["brands"]:
            raise HTTPException(status_code=400, detail="No valid countries found")

        print("Prepared scraper payload with CSV files:", json.dumps(scraper_payload, indent=2))

        # Check if scraper is already running
        if is_scraper_running():
            print("Scraper is currently running, adding to queue")
            
            # For queued items, we need to ensure the CSV files are accessible
            # We'll store the file paths in the payload and let the scraper handle them
            if add_to_queue(scraper_payload):
                return SubmissionResponse(
                    ok=True,
                    message="Data submitted to queue, will start processing once scraper is free",
                    payload=scraper_payload
                )
            else:
                # Clean up temporary files if queue addition failed
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                    except Exception:
                        pass
                raise HTTPException(status_code=500, detail="Failed to add to queue")
        else:
            # Start scraper in background
            import threading
            
            def run_scraper_background():
                try:
                    print("Starting scraper in background with CSV files...")
                    result = run_scraper_main(scraper_payload)
                    print("Scraper completed:", result)
                except Exception as e:
                    print(f"Scraper error: {e}")
                finally:
                    # Clean up temporary files
                    for temp_file in temp_files:
                        try:
                            if os.path.exists(temp_file):
                                os.unlink(temp_file)
                                print(f"Cleaned up temporary file: {temp_file}")
                        except Exception as cleanup_error:
                            print(f"Failed to clean up {temp_file}: {cleanup_error}")

            # Start scraper in background thread
            scraper_thread = threading.Thread(target=run_scraper_background)
            scraper_thread.daemon = True
            scraper_thread.start()

            print("Scraper started successfully in background")
            
            return SubmissionResponse(
                ok=True,
                message="Scraper started successfully in the background with CSV files",
                payload=scraper_payload
            )

    except HTTPException:
        # Clean up temporary files on HTTPException
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception:
                pass
        raise
    except Exception as e:
        # Clean up temporary files on any exception
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception:
                pass
        print(f"Submission processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Submission processing failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4000)
