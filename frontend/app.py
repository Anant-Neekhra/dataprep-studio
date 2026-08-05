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


ui.run(title="DataPrep Studio", host="0.0.0.0", port=8080, reload=True)