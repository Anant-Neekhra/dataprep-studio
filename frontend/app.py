import os

import httpx
from nicegui import ui

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


@ui.page("/")
async def main_page():
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("DataPrep Studio").classes("text-3xl font-bold")
        ui.label("An Interactive, Explainable Data Analysis Workbench").classes(
            "text-gray-500"
        )

        with ui.card().classes("w-96 items-center"):
            ui.label("Backend Connection Status").classes("text-lg font-semibold")

            status_label = ui.label("Checking...").classes("text-gray-400")
            spinner = ui.spinner(size="lg")

            async def check_backend_health():
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(f"{BACKEND_URL}/health")
                        response.raise_for_status()
                        data = response.json()

                    spinner.set_visibility(False)
                    status_label.set_text(
                        f"✅ Connected — {data['app_name']} v{data['version']}"
                    )
                    status_label.classes(replace="text-green-600 font-medium")

                except httpx.RequestError:
                    spinner.set_visibility(False)
                    status_label.set_text(
                        "❌ Could not reach backend. Is it running on port 8000?"
                    )
                    status_label.classes(replace="text-red-600 font-medium")

            ui.timer(0.1, check_backend_health, once=True)

            ui.button(
                "Re-check connection", on_click=check_backend_health
            ).classes("mt-2")

            ui.link("Go to Upload Page →", "/upload").classes("mt-4")


ui.run(title="DataPrep Studio", host="0.0.0.0", port=8080, reload=True)

@ui.page("/upload")
async def upload_page():
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Upload Dataset").classes("text-2xl font-bold")
        ui.link("← Back to home", "/").classes("text-sm text-gray-400")

        overview_container = ui.column().classes("w-full max-w-2xl gap-2")

        async def handle_upload(e):
            overview_container.clear()
            with overview_container:
                ui.label("Uploading...").classes("text-gray-400")

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    files = {"file": (e.name, e.content.read(), "text/csv")}
                    upload_response = await client.post(
                        f"{BACKEND_URL}/datasets/upload", files=files
                    )
                    upload_response.raise_for_status()
                    dataset_id = upload_response.json()["dataset_id"]

                    overview_response = await client.get(
                        f"{BACKEND_URL}/datasets/{dataset_id}/overview"
                    )
                    overview_response.raise_for_status()
                    overview = overview_response.json()

                overview_container.clear()
                with overview_container:
                    with ui.card().classes("w-full"):
                        ui.label(f"📄 {overview['filename']}").classes(
                            "text-lg font-semibold"
                        )
                        with ui.row().classes("gap-8 mt-2"):
                            with ui.column():
                                ui.label("Rows").classes("text-gray-400 text-sm")
                                ui.label(str(overview["rows"])).classes(
                                    "text-xl font-bold"
                                )
                            with ui.column():
                                ui.label("Columns").classes("text-gray-400 text-sm")
                                ui.label(str(overview["columns"])).classes(
                                    "text-xl font-bold"
                                )
                            with ui.column():
                                ui.label("Missing %").classes("text-gray-400 text-sm")
                                ui.label(f"{overview['missing_percentage']}%").classes(
                                    "text-xl font-bold"
                                )
                            with ui.column():
                                ui.label("Duplicate Rows").classes(
                                    "text-gray-400 text-sm"
                                )
                                ui.label(str(overview["duplicate_rows"])).classes(
                                    "text-xl font-bold"
                                )

                    with ui.card().classes("w-full"):
                        ui.label("Feature Types").classes("font-semibold")
                        with ui.row().classes("gap-6 mt-2"):
                            for feature_type, count in overview["feature_types"].items():
                                if count > 0:
                                    ui.label(f"{feature_type}: {count}")

                    with ui.card().classes("w-full"):
                        ui.label("Column Data Types").classes("font-semibold")
                        columns = [
                            {"name": "column", "label": "Column", "field": "column"},
                            {"name": "dtype", "label": "Type", "field": "dtype"},
                        ]
                        rows = [
                            {"column": col, "dtype": dtype}
                            for col, dtype in overview["dtypes"].items()
                        ]
                        ui.table(columns=columns, rows=rows, row_key="column").classes(
                            "w-full mt-2"
                        )

            except httpx.HTTPStatusError as ex:
                overview_container.clear()
                with overview_container:
                    error_detail = ex.response.json().get("detail", "Unknown error")
                    ui.label(f"❌ {error_detail}").classes("text-red-600")

        ui.upload(on_upload=handle_upload, auto_upload=True).classes(
            "max-w-full"
        ).props("accept=.csv")