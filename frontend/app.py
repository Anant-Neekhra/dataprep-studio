import os

import httpx
from nicegui import ui
import plotly.graph_objects as go
from nicegui import app as nicegui_app

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

def dataset_nav_links(dataset_id: str, current_page: str = ""):
    """
    Renders a consistent set of cross-links to every dataset-scoped page.
    Called at the top of every page below Upload, so navigation is
    identical everywhere instead of ad-hoc per page. current_page can be
    used to skip linking to the page you're already on.
    """
    links = [
        ("Column Types & Drop Columns", "column-types"),
        ("Recommendations", "recommendations"),
        ("Correlation Analysis", "correlation"),
        ("Categorical Analysis", "categorical"),
        ("Feature Inspector", "inspect"),
        ("Visualization Center", "visualize"),
        ("Version History", "history"),
        ("Pipeline View", "pipeline"),
        ("Export", "export"),
    ]
    with ui.row().classes("gap-4 flex-wrap justify-center max-w-2xl"):
        for label, path in links:
            if path == current_page:
                continue
            ui.link(f"{label} →", f"/{path}/{dataset_id}").classes(
                "text-sm text-blue-600"
            )

def learning_mode_toggle():
    """
    Renders a Learning Mode switch that persists across page navigation
    within the same browser session, via NiceGUI's per-user storage
    (distinct from your backend's dataset storage — this is purely a
    frontend UI preference, never sent to the API).
    """
    is_on = nicegui_app.storage.user.get("learning_mode", False)

    def on_toggle(e):
        nicegui_app.storage.user["learning_mode"] = e.value

    ui.switch("Learning Mode", value=is_on, on_change=on_toggle).classes("text-sm")


def is_learning_mode() -> bool:
    return nicegui_app.storage.user.get("learning_mode", False)

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

@ui.page("/upload")
async def upload_page():
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Upload Dataset").classes("text-2xl font-bold")
        ui.link("← Back to home", "/").classes("text-sm text-gray-400")

        ui.label("Or continue with a previous dataset:").classes("text-sm text-gray-500 mt-2")
        dataset_list_container = ui.column().classes("w-full max-w-2xl gap-1")

        async def load_dataset_list():
            dataset_list_container.clear()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets")
                if response.status_code == 200:
                    datasets = response.json()["datasets"]
                    with dataset_list_container:
                        if not datasets:
                            ui.label("No previous datasets yet.").classes(
                                "text-xs text-gray-400"
                            )
                        for d in datasets:
                            with ui.row().classes("items-center gap-2"):
                                ui.link(
                                    d["filename"], f"/column-types/{d['dataset_id']}"
                                ).classes("text-sm text-blue-600")
                                version_label = f"v{d['current_version']}/{d['total_versions']}"
                                version_label += " (edited)" if d["total_versions"] > 1 else " (unedited)"
                                ui.label(version_label).classes("text-xs text-gray-500")
                                ui.label(d["created_at"][:19]).classes("text-xs text-gray-400")

                                async def delete_this_dataset(dataset_id=d["dataset_id"], filename=d["filename"]):
                                    async with httpx.AsyncClient(timeout=15.0) as client:
                                        response = await client.delete(
                                            f"{BACKEND_URL}/datasets/{dataset_id}"
                                        )
                                        if response.status_code != 200:
                                            try:
                                                detail = response.json().get("detail", "Unknown error")
                                            except Exception:
                                                detail = f"Request failed ({response.status_code})"
                                            ui.notify(detail, type="negative")
                                            return
                                    ui.notify(f"Deleted '{filename}'", type="positive")
                                    await load_dataset_list()

                                ui.button(icon="delete", on_click=delete_this_dataset).props(
                                    "flat dense round color=negative size=sm"
                                )

        ui.timer(0.1, load_dataset_list, once=True)

        ui.separator().classes("my-2")

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

                    ui.link(
                        "Review & Override Column Types →", f"/column-types/{dataset_id}"
                    ).classes("mt-2")

            except httpx.HTTPStatusError as ex:
                overview_container.clear()
                with overview_container:
                    error_detail = ex.response.json().get("detail", "Unknown error")
                    ui.label(f"❌ {error_detail}").classes("text-red-600")

        ui.upload(on_upload=handle_upload, auto_upload=True).classes(
            "max-w-full"
        ).props("accept=.csv")

@ui.page("/column-types/{dataset_id}")
async def column_types_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Column Type Review").classes("text-2xl font-bold")
        ui.label(
            "Auto-detection isn't always right — especially for ID-like columns. "
            "Review and override below."
        ).classes("text-sm text-gray-400 text-center max-w-xl")
        ui.link("← Back to upload", "/upload").classes("text-sm text-gray-400")
        dataset_nav_links(dataset_id, current_page="column-types")

        table_container = ui.column().classes("w-full max-w-3xl gap-2")

        type_options = [
            "numerical", "categorical", "boolean", "datetime", "text", "id", "multi_label", "mixed"
        ]

        async def load_column_types():
            table_container.clear()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/column-types")
                response.raise_for_status()
                column_types = response.json()

            with table_container:
                for col_info in column_types:
                    with ui.card().classes("w-full"):
                        with ui.row().classes("w-full items-center justify-between"):
                            with ui.column().classes("gap-0"):
                                ui.label(col_info["column"]).classes("font-semibold")
                                ui.label(f"pandas dtype: {col_info['pandas_dtype']}").classes(
                                    "text-xs text-gray-400"
                                )
                                detected_line = f"Detected: {col_info['detected_type']}"
                                if col_info["is_overridden"]:
                                    detected_line += f"  →  Overridden: {col_info['effective_type']}"
                                ui.label(detected_line).classes(
                                    "text-xs "
                                    + ("text-orange-500" if col_info["is_overridden"] else "text-gray-500")
                                )

                            with ui.row().classes("items-center gap-2"):
                                select = ui.select(
                                    options=type_options,
                                    value=col_info["effective_type"],
                                ).classes("w-40")

                                async def apply_override(
                                    column=col_info["column"], select=select
                                ):
                                    async with httpx.AsyncClient(timeout=15.0) as client:
                                        await client.put(
                                            f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column}/type",
                                            json={"logical_type": select.value},
                                        )
                                    ui.notify(f"'{column}' set to '{select.value}'", type="positive")
                                    await load_column_types()

                                async def reset_override(column=col_info["column"]):
                                    async with httpx.AsyncClient(timeout=15.0) as client:
                                        await client.delete(
                                            f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column}/type"
                                        )
                                    ui.notify(f"'{column}' reset to auto-detected", type="info")
                                    await load_column_types()

                                ui.button("Apply", on_click=apply_override).props("dense")
                                if col_info["is_overridden"]:
                                    ui.button("Reset", on_click=reset_override).props(
                                        "dense flat"
                                    )

                                async def drop_this_column(column=col_info["column"]):
                                    async with httpx.AsyncClient(timeout=15.0) as client:
                                        response = await client.delete(
                                            f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column}"
                                        )
                                        if response.status_code != 200:
                                            try:
                                                detail = response.json().get("detail", "Unknown error")
                                            except Exception:
                                                detail = f"Request failed ({response.status_code})"
                                            ui.notify(detail, type="negative")
                                            return
                                    ui.notify(f"Dropped '{column}'", type="positive")
                                    await load_column_types()

                                ui.button("Drop Column", on_click=drop_this_column).props(
                                    "dense flat color=negative"
                                )

        ui.timer(0.1, load_column_types, once=True)

SEVERITY_COLORS = {
    "high": "text-red-600",
    "medium": "text-orange-500",
    "low": "text-gray-500",
}


@ui.page("/recommendations/{dataset_id}")
async def recommendations_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Recommendations").classes("text-2xl font-bold")
        ui.label(
            "Every suggestion below is generated by deterministic rules — "
            "not AI. Expand any card to see the full reasoning."
        ).classes("text-sm text-gray-400 text-center max-w-xl")
        ui.link("← Back to upload", "/upload").classes("text-sm text-gray-400")
        dataset_nav_links(dataset_id, current_page="recommendations")
        learning_mode_toggle()

        cards_container = ui.column().classes("w-full max-w-3xl gap-3")

        async def load_recommendations():
            cards_container.clear()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{BACKEND_URL}/datasets/{dataset_id}/recommendations"
                )
                response.raise_for_status()
                recommendations = response.json()

            with cards_container:
                if not recommendations:
                    ui.label("No issues detected — this dataset looks clean!").classes(
                        "text-green-600"
                    )
                    return

                for rec in recommendations:
                    severity_color = SEVERITY_COLORS.get(rec["severity"], "text-gray-500")
                    with ui.card().classes("w-full"):
                        with ui.row().classes("w-full items-center justify-between"):
                            with ui.column().classes("gap-0"):
                                ui.label(
                                    f"{rec['column']} — {rec['recommendation']}"
                                ).classes("font-semibold")
                                ui.label(
                                    f"{rec['severity'].upper()} · {rec['category']}"
                                ).classes(f"text-xs {severity_color} font-medium")

                        with ui.expansion("Why? See full reasoning").classes("w-full mt-2"):
                            ui.label("Reason").classes("font-semibold text-sm mt-1")
                            ui.label(rec["reason"]).classes("text-sm text-gray-600")

                            if rec["advantages"]:
                                ui.label("Advantages").classes(
                                    "font-semibold text-sm mt-2 text-green-700"
                                )
                                for adv in rec["advantages"]:
                                    ui.label(f"• {adv}").classes("text-sm text-gray-600")

                            if rec["disadvantages"]:
                                ui.label("Disadvantages").classes(
                                    "font-semibold text-sm mt-2 text-red-700"
                                )
                                for dis in rec["disadvantages"]:
                                    ui.label(f"• {dis}").classes("text-sm text-gray-600")

                            if rec["alternatives"]:
                                ui.label("Alternatives").classes(
                                    "font-semibold text-sm mt-2"
                                )
                                ui.label(", ".join(rec["alternatives"])).classes(
                                    "text-sm text-gray-600"
                                )

                            if rec["docs_url"]:
                                ui.link("📄 Official Documentation", rec["docs_url"]).classes(
                                    "text-sm mt-2 text-blue-600"
                                )

                            if is_learning_mode() and rec.get("learning_content"):
                                lc = rec["learning_content"]
                                ui.separator().classes("my-2")
                                ui.label("📚 Learn More").classes(
                                    "font-semibold text-sm text-purple-700"
                                )
                                ui.label(lc["concept"]).classes("text-sm font-medium mt-1")
                                ui.label(lc["why_it_matters"]).classes("text-sm text-gray-600 mt-1")

                                if lc.get("math_explanation"):
                                    ui.label("The Math").classes(
                                        "text-xs font-semibold text-gray-500 mt-2"
                                    )
                                    ui.label(lc["math_explanation"]).classes(
                                        "text-sm text-gray-600"
                                    )

                                if lc.get("common_mistakes"):
                                    ui.label("Common Mistakes").classes(
                                        "text-xs font-semibold text-gray-500 mt-2"
                                    )
                                    for mistake in lc["common_mistakes"]:
                                        ui.label(f"⚠ {mistake}").classes("text-sm text-gray-600")

                                if lc.get("real_world_example"):
                                    ui.label("Real-World Example").classes(
                                        "text-xs font-semibold text-gray-500 mt-2"
                                    )
                                    ui.label(lc["real_world_example"]).classes(
                                        "text-sm text-gray-600"
                                    )

                        if rec["category"] == "missing_values":
                            ui.link(
                                "Go handle this →", f"/missing-values/{dataset_id}"
                            ).classes("text-sm text-blue-600 mt-2")

                        if rec["category"] == "data_quality" and "duplicate" in rec["rule_id"]:
                            ui.link(
                                "Go handle this →", f"/duplicates/{dataset_id}"
                            ).classes("text-sm text-blue-600 mt-2")

                        if rec["category"] == "datatype":
                            ui.link(
                                "Go handle this →", f"/datatypes/{dataset_id}"
                            ).classes("text-sm text-blue-600 mt-2")

                        if rec["category"] == "distribution":
                            ui.link(
                                "Go handle this →", f"/distribution/{dataset_id}"
                            ).classes("text-sm text-blue-600 mt-2")

                        if rec["category"] == "outliers":
                            ui.link(
                                "Go handle this →", f"/outliers/{dataset_id}"
                            ).classes("text-sm text-blue-600 mt-2")

                        if rec["category"] == "correlation":
                            ui.link(
                                "Go handle this →", f"/correlation/{dataset_id}"
                            ).classes("text-sm text-blue-600 mt-2")

                        if rec["category"] == "encoding":
                            ui.link(
                                "Go handle this →", f"/encoding/{dataset_id}"
                            ).classes("text-sm text-blue-600 mt-2")
                        if rec["category"] == "scaling":
                            ui.link(
                                "Go handle this →", f"/scaling/{dataset_id}"
                            ).classes("text-sm text-blue-600 mt-2")

        ui.timer(0.1, load_recommendations, once=True)

IMPUTE_STRATEGIES = ["mean", "median", "mode", "constant", "forward_fill", "backward_fill", "drop_rows"]


@ui.page("/missing-values/{dataset_id}")
async def missing_values_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Missing Value Engine").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        column_select = ui.select([], label="Column").classes("w-80")
        strategy_select = ui.select(IMPUTE_STRATEGIES, value="median", label="Strategy").classes(
            "w-80"
        )

        async def load_columns():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/column-types")
                if response.status_code == 200:
                    column_names = [c["column"] for c in response.json()]
                    column_select.set_options(column_names)
                    if column_names:
                        column_select.set_value(column_names[0])

        ui.timer(0.1, load_columns, once=True)
        constant_input = ui.input("Constant value (only for 'constant' strategy)").classes("w-80")

        result_container = ui.column().classes("w-full max-w-2xl gap-3")

        def stats_row(label: str, stats: dict):
            with ui.row().classes("gap-6"):
                with ui.column().classes("gap-0"):
                    ui.label(label).classes("text-xs text-gray-400")
                    ui.label(f"Mean: {stats.get('mean')}").classes("text-sm")
                    ui.label(f"Median: {stats.get('median')}").classes("text-sm")
                    ui.label(f"Missing: {stats['missing_count']} / {stats['row_count']}").classes(
                        "text-sm"
                    )

        async def do_preview():
            result_container.clear()
            body = {"strategy": strategy_select.value, "constant_value": constant_input.value or None}
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/impute/preview",
                    json=body,
                )
                if response.status_code != 200:
                    try:
                        error_detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        error_detail = f"Request failed ({response.status_code})"
                    with result_container:
                        ui.label(f"❌ {error_detail}").classes("text-red-600")
                    return
                preview = response.json()

            with result_container:
                with ui.card().classes("w-full"):
                    ui.label(f"Preview — {strategy_select.value} on '{column_select.value}'").classes(
                        "font-semibold"
                    )
                    with ui.row().classes("gap-8 mt-2"):
                        stats_row("Before", preview["before"])
                        stats_row("After", preview["after"])
                    ui.label(f"Sample before: {preview['sample_before']}").classes(
                        "text-xs text-gray-500 mt-2"
                    )
                    ui.label(f"Sample after: {preview['sample_after']}").classes(
                        "text-xs text-gray-500"
                    )

        async def do_apply():
            body = {"strategy": strategy_select.value, "constant_value": constant_input.value or None}
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/impute/apply",
                    json=body,
                )
                if response.status_code != 200:
                    try:
                        error_detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        error_detail = f"Request failed ({response.status_code})"
                    with result_container:
                        ui.label(f"❌ {error_detail}").classes("text-red-600")
                    return
                overview = response.json()
            ui.notify(
                f"Applied. Dataset now has {overview['missing_percentage']}% missing overall.",
                type="positive",
            )

        with ui.row().classes("gap-2"):
            ui.button("Preview", on_click=do_preview)
            ui.button("Apply", on_click=do_apply).props("color=positive")

        ui.separator().classes("my-4")

        ui.label('"Why Not?" — Compare Two Strategies').classes("text-lg font-semibold")
        with ui.row().classes("gap-2"):
            strategy_a_select = ui.select(IMPUTE_STRATEGIES, value="mean", label="Strategy A")
            strategy_b_select = ui.select(IMPUTE_STRATEGIES, value="median", label="Strategy B")

        compare_container = ui.column().classes("w-full max-w-2xl gap-3")

        async def do_compare():
            compare_container.clear()
            body = {"strategy_a": strategy_a_select.value, "strategy_b": strategy_b_select.value}
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/impute/compare",
                    json=body,
                )
                if response.status_code != 200:
                    try:
                        error_detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        error_detail = f"Request failed ({response.status_code})"
                    with compare_container:
                        ui.label(f"❌ {error_detail}").classes("text-red-600")
                    return
                comparison = response.json()

            with compare_container:
                with ui.card().classes("w-full"):
                    with ui.row().classes("gap-8"):
                        stats_row("Before", comparison["before"])
                        stats_row(f"After {strategy_a_select.value}", comparison["after_a"])
                        stats_row(f"After {strategy_b_select.value}", comparison["after_b"])

        ui.button("Compare", on_click=do_compare)

ui.run(title="DataPrep Studio", host="0.0.0.0", port=8080, reload=True, storage_secret="dev-secret-change-in-production")

@ui.page("/duplicates/{dataset_id}")
async def duplicates_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Duplicate Analysis").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        # --- Duplicate Rows ---
        ui.label("Duplicate Rows").classes("text-lg font-semibold mt-4")
        rows_container = ui.column().classes("w-full max-w-2xl gap-2")

        async def load_row_duplicates():
            rows_container.clear()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{BACKEND_URL}/datasets/{dataset_id}/duplicates/rows/preview"
                )
                response.raise_for_status()
                preview = response.json()

            with rows_container:
                with ui.card().classes("w-full"):
                    ui.label(
                        f"{preview['duplicate_count']} duplicate rows "
                        f"({preview['duplicate_percentage']}%) — "
                        f"{preview['rows_after_removal']} rows would remain"
                    ).classes("text-sm")

                    if preview["sample_duplicate_rows"]:
                        ui.label("Sample duplicate rows:").classes("text-xs text-gray-400 mt-2")
                        for row in preview["sample_duplicate_rows"]:
                            ui.label(str(row)).classes("text-xs text-gray-600")

                    keep_select = ui.select(["first", "last"], value="first", label="Keep")

                    async def remove_row_duplicates():
                        async with httpx.AsyncClient(timeout=15.0) as client:
                            response = await client.post(
                                f"{BACKEND_URL}/datasets/{dataset_id}/duplicates/rows/apply",
                                json={"keep": keep_select.value},
                            )
                            if response.status_code != 200:
                                try:
                                    detail = response.json().get("detail", "Unknown error")
                                except Exception:
                                    detail = f"Request failed ({response.status_code})"
                                ui.notify(detail, type="negative")
                                return
                            overview = response.json()
                        ui.notify(
                            f"Removed. Dataset now has {overview['duplicate_rows']} duplicate rows.",
                            type="positive",
                        )
                        await load_row_duplicates()

                    ui.button("Remove Duplicate Rows", on_click=remove_row_duplicates).props(
                        "color=positive"
                    ).classes("mt-2")

        ui.timer(0.1, load_row_duplicates, once=True)

        ui.separator().classes("my-4")

        # --- Duplicate Columns ---
        ui.label("Duplicate Columns").classes("text-lg font-semibold")
        columns_container = ui.column().classes("w-full max-w-2xl gap-2")

        async def load_column_duplicates():
            columns_container.clear()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{BACKEND_URL}/datasets/{dataset_id}/duplicates/columns/preview"
                )
                response.raise_for_status()
                preview = response.json()

            with columns_container:
                if not preview["pairs"]:
                    ui.label("No duplicate columns found.").classes("text-sm text-gray-500")
                    return

                for pair in preview["pairs"]:
                    with ui.card().classes("w-full"):
                        ui.label(
                            f"'{pair['column_a']}' and '{pair['column_b']}' are identical"
                        ).classes("text-sm")

                        async def drop_one(col_to_drop=pair["column_b"]):
                            async with httpx.AsyncClient(timeout=15.0) as client:
                                response = await client.post(
                                    f"{BACKEND_URL}/datasets/{dataset_id}/duplicates/columns/apply",
                                    json={"columns_to_drop": [col_to_drop]},
                                )
                                if response.status_code != 200:
                                    try:
                                        detail = response.json().get("detail", "Unknown error")
                                    except Exception:
                                        detail = f"Request failed ({response.status_code})"
                                    ui.notify(detail, type="negative")
                                    return
                            ui.notify(f"Dropped '{col_to_drop}'", type="positive")
                            await load_column_duplicates()

                        ui.button(
                            f"Drop '{pair['column_b']}' (keep '{pair['column_a']}')",
                            on_click=drop_one,
                        ).props("dense")

        ui.timer(0.1, load_column_duplicates, once=True)

DTYPE_OPTIONS = ["datetime", "integer", "category", "float", "string"]


@ui.page("/datatypes/{dataset_id}")
async def datatypes_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Datatype Analyzer").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        column_select = ui.select([], label="Column").classes("w-80")
        target_select = ui.select(DTYPE_OPTIONS, value="datetime", label="Convert to").classes(
            "w-80"
        )

        async def load_columns():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/column-types")
                if response.status_code == 200:
                    names = [c["column"] for c in response.json()]
                    column_select.set_options(names)
                    if names:
                        column_select.set_value(names[0])

        ui.timer(0.1, load_columns, once=True)

        result_container = ui.column().classes("w-full max-w-2xl gap-3")

        async def do_preview():
            result_container.clear()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/convert/preview",
                    json={"target_type": target_select.value},
                )
                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        detail = f"Request failed ({response.status_code})"
                    with result_container:
                        ui.label(f"❌ {detail}").classes("text-red-600")
                    return
                preview = response.json()

            with result_container:
                with ui.card().classes("w-full"):
                    ui.label(
                        f"{preview['before_dtype']} → {preview['after_dtype']}"
                    ).classes("font-semibold")
                    ui.label(
                        f"Missing before: {preview['before_missing']} | "
                        f"Missing after: {preview['after_missing']} | "
                        f"Newly invalid: {preview['newly_invalid_count']}"
                    ).classes("text-sm text-gray-600")
                    ui.label(f"Sample before: {preview['sample_before']}").classes(
                        "text-xs text-gray-500 mt-2"
                    )
                    ui.label(f"Sample after: {preview['sample_after']}").classes(
                        "text-xs text-gray-500"
                    )

        async def do_apply():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/convert/apply",
                    json={"target_type": target_select.value},
                )
                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        detail = f"Request failed ({response.status_code})"
                    ui.notify(detail, type="negative")
                    return
            ui.notify("Conversion applied.", type="positive")

        with ui.row().classes("gap-2"):
            ui.button("Preview", on_click=do_preview)
            ui.button("Apply", on_click=do_apply).props("color=positive")


TRANSFORM_OPTIONS = ["none", "log", "sqrt", "box_cox", "yeo_johnson"]


def make_histogram_figure(bin_edges: list, counts: list, title: str) -> go.Figure:
    bin_centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(counts))]
    fig = go.Figure(data=[go.Bar(x=bin_centers, y=counts)])
    fig.update_layout(title=title, height=300, margin=dict(l=20, r=20, t=40, b=20))
    return fig


@ui.page("/distribution/{dataset_id}")
async def distribution_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Distribution Analysis").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        column_select = ui.select([], label="Numeric Column").classes("w-80")

        async def load_numeric_columns():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/column-types")
                if response.status_code == 200:
                    names = [
                        c["column"] for c in response.json() if c["effective_type"] == "numerical"
                    ]
                    column_select.set_options(names)
                    if names:
                        column_select.set_value(names[0])

        ui.timer(0.1, load_numeric_columns, once=True)

        analysis_container = ui.column().classes("w-full max-w-2xl gap-3")

        async def load_distribution():
            analysis_container.clear()
            if not column_select.value:
                return
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/distribution"
                )
                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        detail = f"Request failed ({response.status_code})"
                    with analysis_container:
                        ui.label(f"❌ {detail}").classes("text-red-600")
                    return
                dist = response.json()

            with analysis_container:
                with ui.card().classes("w-full"):
                    ui.label(f"Skewness: {dist['skewness']}  |  Kurtosis: {dist['kurtosis']}").classes(
                        "text-sm"
                    )
                    norm = dist["normality_test"]
                    if norm["is_normal"] is not None:
                        ui.label(
                            f"Shapiro-Wilk p-value: {norm['p_value']:.4f} — "
                            f"{'Likely normal' if norm['is_normal'] else 'Not normally distributed'}"
                        ).classes("text-sm text-gray-600")

                    fig = make_histogram_figure(
                        dist["histogram"]["bin_edges"], dist["histogram"]["counts"], column_select.value
                    )
                    ui.plotly(fig).classes("w-full")

        column_select.on("update:model-value", lambda: load_distribution())
        ui.timer(0.5, load_distribution, once=True)

        ui.separator().classes("my-4")

        ui.label("Apply a Transform").classes("text-lg font-semibold")
        transform_select = ui.select(TRANSFORM_OPTIONS, value="log", label="Transform")

        transform_result = ui.column().classes("w-full max-w-2xl gap-3")

        async def do_transform_preview():
            transform_result.clear()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/transform/preview",
                    json={"transform": transform_select.value},
                )
                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        detail = f"Request failed ({response.status_code})"
                    with transform_result:
                        ui.label(f"❌ {detail}").classes("text-red-600")
                    return
                preview = response.json()

            with transform_result:
                with ui.card().classes("w-full"):
                    ui.label(
                        f"Skewness: {preview['before_skewness']} → {preview['after_skewness']}"
                    ).classes("font-semibold")
                    with ui.row().classes("w-full gap-4"):
                        ui.plotly(
                            make_histogram_figure(
                                preview["before_histogram"]["bin_edges"],
                                preview["before_histogram"]["counts"],
                                "Before",
                            )
                        ).classes("flex-1")
                        ui.plotly(
                            make_histogram_figure(
                                preview["after_histogram"]["bin_edges"],
                                preview["after_histogram"]["counts"],
                                "After",
                            )
                        ).classes("flex-1")

        async def do_transform_apply():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/transform/apply",
                    json={"transform": transform_select.value},
                )
                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        detail = f"Request failed ({response.status_code})"
                    ui.notify(detail, type="negative")
                    return
            ui.notify("Transform applied.", type="positive")
            await load_distribution()

        with ui.row().classes("gap-2"):
            ui.button("Preview Transform", on_click=do_transform_preview)
            ui.button("Apply Transform", on_click=do_transform_apply).props("color=positive")

OUTLIER_METHODS_LIST = ["iqr", "zscore", "modified_zscore"]


@ui.page("/outliers/{dataset_id}")
async def outliers_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Outlier Analysis").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        column_select = ui.select([], label="Numeric Column").classes("w-80")
        method_select = ui.select(OUTLIER_METHODS_LIST, value="iqr", label="Detection Method").classes(
            "w-80"
        )

        async def load_numeric_columns():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/column-types")
                if response.status_code == 200:
                    names = [
                        c["column"] for c in response.json() if c["effective_type"] == "numerical"
                    ]
                    column_select.set_options(names)
                    if names:
                        column_select.set_value(names[0])

        ui.timer(0.1, load_numeric_columns, once=True)

        result_container = ui.column().classes("w-full max-w-2xl gap-3")

        async def load_outliers():
            result_container.clear()
            if not column_select.value:
                return
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/outliers",
                    params={"method": method_select.value},
                )
                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        detail = f"Request failed ({response.status_code})"
                    with result_container:
                        ui.label(f"❌ {detail}").classes("text-red-600")
                    return
                result = response.json()

            with result_container:
                with ui.card().classes("w-full"):
                    ui.label(
                        f"{result['outlier_count']} outliers ({result['outlier_percentage']}%) "
                        f"using {result['method']}"
                    ).classes("font-semibold")
                    if result["outlier_values"]:
                        ui.label(f"Sample values: {result['outlier_values'][:10]}").classes(
                            "text-xs text-gray-500 mt-2"
                        )

                    with ui.row().classes("gap-2 mt-3"):
                        async def remove_outliers_action():
                            await treat_outliers("remove")

                        async def cap_outliers_action():
                            await treat_outliers("cap")

                        async def treat_outliers(action: str):
                            async with httpx.AsyncClient(timeout=15.0) as client:
                                response = await client.post(
                                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/outliers/apply",
                                    json={"method": method_select.value, "action": action},
                                )
                                if response.status_code != 200:
                                    try:
                                        detail = response.json().get("detail", "Unknown error")
                                    except Exception:
                                        detail = f"Request failed ({response.status_code})"
                                    ui.notify(detail, type="negative")
                                    return
                            ui.notify(f"Outliers {action}d.", type="positive")
                            await load_outliers()

                        ui.button("Cap Outliers", on_click=cap_outliers_action).props(
                            "color=positive"
                        )
                        ui.button("Remove Outlier Rows", on_click=remove_outliers_action).props(
                            "color=negative"
                        )

        column_select.on("update:model-value", lambda: load_outliers())
        method_select.on("update:model-value", lambda: load_outliers())
        ui.timer(0.5, load_outliers, once=True)

CORRELATION_METHODS = ["pearson", "spearman", "kendall"]


@ui.page("/correlation/{dataset_id}")
async def correlation_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Correlation Analysis").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        with ui.row().classes("gap-4 items-end"):
            method_select = ui.select(CORRELATION_METHODS, value="pearson", label="Method").classes(
                "w-60"
            )
            threshold_input = ui.number(
                label="High Correlation Threshold (changes just for visualization)", value=0.8, min=0.0, max=1.0, step=0.05
            ).classes("w-60")

        heatmap_container = ui.column().classes("w-full max-w-3xl gap-3")

        correlation_request_id = {"value": 0}

        async def load_correlation():
            correlation_request_id["value"] += 1
            my_request_id = correlation_request_id["value"]

            async with httpx.AsyncClient(timeout=15.0) as client:
                corr_response = await client.get(
                    f"{BACKEND_URL}/datasets/{dataset_id}/correlation",
                    params={"method": method_select.value},
                )
                pairs_response = await client.get(
                    f"{BACKEND_URL}/datasets/{dataset_id}/correlation/high-pairs",
                    params={"threshold": threshold_input.value},
                )

            # If a newer request started while we were waiting on the
            # network, this response is stale — discard it instead of
            # rendering, so only the LATEST request's result ever
            # reaches the container. This is what prevents duplicate
            # or out-of-order charts when the threshold input fires
            # multiple rapid events (e.g. one per keystroke).
            if my_request_id != correlation_request_id["value"]:
                return

            heatmap_container.clear()

            if corr_response.status_code != 200:
                with heatmap_container:
                    ui.label("❌ Could not load correlation matrix.").classes("text-red-600")
                return

            corr = corr_response.json()

            with heatmap_container:
                if len(corr["columns"]) < 2:
                    ui.label(
                        "Not enough numerical columns for a correlation matrix."
                    ).classes("text-sm text-gray-500")
                    return

                fig = go.Figure(
                    data=go.Heatmap(
                        z=corr["matrix"],
                        x=corr["columns"],
                        y=corr["columns"],
                        colorscale="RdBu",
                        zmid=0,
                        zmin=-1,
                        zmax=1,
                        text=corr["matrix"],
                        texttemplate="%{text}",
                        textfont={"size": 10},
                    )
                )
                fig.update_layout(
                    title=f"{method_select.value.capitalize()} Correlation",
                    height=500,
                    margin=dict(l=20, r=20, t=40, b=20),
                )
                ui.plotly(fig).classes("w-full")

                if pairs_response.status_code == 200:
                    pairs = pairs_response.json()["pairs"]
                    if pairs:
                        with ui.card().classes("w-full mt-2"):
                            ui.label(
                                f"High Correlation Pairs (|r| ≥ {threshold_input.value})"
                            ).classes("font-semibold")
                            for p in pairs:
                                ui.label(
                                    f"{p['column_a']} ↔ {p['column_b']}: {p['correlation']}"
                                ).classes("text-sm text-gray-600")
                    else:
                        ui.label(
                            f"No pairs above the {threshold_input.value} threshold."
                        ).classes("text-sm text-gray-500 mt-2")

        method_select.on("update:model-value", lambda: load_correlation())
        threshold_input.on("update:model-value", lambda: load_correlation())
        ui.timer(0.1, load_correlation, once=True)

@ui.page("/categorical/{dataset_id}")
async def categorical_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Categorical Analysis").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        column_select = ui.select([], label="Column").classes("w-80")

        async def load_categorical_columns():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/column-types")
                if response.status_code == 200:
                    names = [
                        c["column"] for c in response.json()
                        if c["effective_type"] in ("categorical", "multi_label")
                    ]
                    column_select.set_options(names)
                    if names:
                        column_select.set_value(names[0])

        ui.timer(0.1, load_categorical_columns, once=True)

        result_container = ui.column().classes("w-full max-w-2xl gap-3")
        request_id = {"value": 0}

        async def load_analysis():
            request_id["value"] += 1
            my_id = request_id["value"]
            if not column_select.value:
                return

            async with httpx.AsyncClient(timeout=15.0) as client:
                types_response = await client.get(
                    f"{BACKEND_URL}/datasets/{dataset_id}/column-types"
                )
                col_info = next(
                    (c for c in types_response.json() if c["column"] == column_select.value), None
                )
                is_multi_label = col_info and col_info["effective_type"] == "multi_label"

                if is_multi_label:
                    response = await client.get(
                        f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/multi-label-profile"
                    )
                else:
                    response = await client.get(
                        f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/category-frequencies"
                    )

            if my_id != request_id["value"]:
                return  # stale request, discard (same guard as Day 11)

            result_container.clear()

            if response.status_code != 200:
                try:
                    detail = response.json().get("detail", "Unknown error")
                except Exception:
                    detail = f"Request failed ({response.status_code})"
                with result_container:
                    ui.label(f"❌ {detail}").classes("text-red-600")
                return

            data = response.json()

            with result_container:
                if is_multi_label:
                    with ui.card().classes("w-full"):
                        ui.label(f"Multi-Label Column (delimiter: '{data['delimiter']}')").classes(
                            "font-semibold"
                        )
                        ui.label(
                            f"Vocabulary size: {data['vocabulary_size']}  |  "
                            f"Avg labels per row: {data['avg_labels_per_row']}"
                        ).classes("text-sm text-gray-600")

                        labels = list(data["label_frequencies"].keys())
                        counts = list(data["label_frequencies"].values())
                        fig = go.Figure(data=[go.Bar(x=labels, y=counts)])
                        fig.update_layout(
                            title="Label Frequencies", height=350,
                            margin=dict(l=20, r=20, t=40, b=20)
                        )
                        ui.plotly(fig).classes("w-full")
                else:
                    with ui.card().classes("w-full"):
                        ui.label(f"{data['total_unique']} unique categories").classes(
                            "font-semibold"
                        )
                        fig = go.Figure(
                            data=[go.Bar(x=data["categories"], y=data["counts"])]
                        )
                        fig.update_layout(
                            title="Category Frequencies", height=350,
                            margin=dict(l=20, r=20, t=40, b=20)
                        )
                        ui.plotly(fig).classes("w-full")

        column_select.on("update:model-value", lambda: load_analysis())
        ui.timer(0.5, load_analysis, once=True)

@ui.page("/inspect/{dataset_id}")
async def inspect_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Feature Inspector").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        column_select = ui.select([], label="Column").classes("w-80")

        async def load_columns():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/column-types")
                if response.status_code == 200:
                    names = [c["column"] for c in response.json()]
                    column_select.set_options(names)
                    if names:
                        column_select.set_value(names[0])

        ui.timer(0.1, load_columns, once=True)

        report_container = ui.column().classes("w-full max-w-3xl gap-3")
        request_id = {"value": 0}

        async def load_report():
            request_id["value"] += 1
            my_id = request_id["value"]
            if not column_select.value:
                return

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/inspect"
                )

            if my_id != request_id["value"]:
                return

            report_container.clear()

            if response.status_code != 200:
                try:
                    detail = response.json().get("detail", "Unknown error")
                except Exception:
                    detail = f"Request failed ({response.status_code})"
                with report_container:
                    ui.label(f"❌ {detail}").classes("text-red-600")
                return

            r = response.json()

            with report_container:
                with ui.card().classes("w-full"):
                    ui.label(f"{r['column']}").classes("text-xl font-bold")
                    type_line = f"pandas: {r['pandas_dtype']}  |  effective type: {r['effective_type']}"
                    if r["is_overridden"]:
                        type_line += f" (overridden from {r['detected_type']})"
                    ui.label(type_line).classes("text-sm text-gray-500")
                    ui.label(f"Memory: {r['memory_usage_bytes']:,} bytes").classes(
                        "text-xs text-gray-400"
                    )

                with ui.card().classes("w-full"):
                    ui.label("Profile").classes("font-semibold")
                    p = r["profile"]
                    ui.label(
                        f"Count: {p['count']}  |  Missing: {p['missing_percentage']}%  |  "
                        f"Unique: {p['unique_count']}  |  Cardinality ratio: {p['cardinality_ratio']}"
                    ).classes("text-sm")
                    if r["entropy"] is not None:
                        ui.label(f"Entropy: {r['entropy']} bits").classes("text-sm")
                    if p.get("mean") is not None:
                        ui.label(
                            f"Mean: {p['mean']}  |  Median: {p['median']}  |  Std: {p['std']}  |  "
                            f"Skewness: {p['skewness']}  |  Kurtosis: {p['kurtosis']}"
                        ).classes("text-sm")

                quality = r["quality_flags"]
                active_flags = [k.replace("_", " ") for k, v in quality.items() if v]
                if active_flags:
                    with ui.card().classes("w-full"):
                        ui.label("Quality Flags").classes("font-semibold text-orange-600")
                        ui.label(", ".join(active_flags)).classes("text-sm")

                if r["outlier_summary"]:
                    with ui.card().classes("w-full"):
                        ui.label("Outliers (IQR method)").classes("font-semibold")
                        ui.label(
                            f"{r['outlier_summary']['outlier_count']} outliers "
                            f"({r['outlier_summary']['outlier_percentage']}%)"
                        ).classes("text-sm")

                if r["top_correlated_columns"]:
                    with ui.card().classes("w-full"):
                        ui.label("Top Correlated Columns").classes("font-semibold")
                        for c in r["top_correlated_columns"]:
                            ui.label(f"{c['column']}: {c['correlation']}").classes("text-sm")

                if r["possible_transformations"]:
                    with ui.card().classes("w-full"):
                        ui.label("Possible Transformations").classes("font-semibold")
                        for t in r["possible_transformations"]:
                            ui.label(f"• {t}").classes("text-sm text-gray-600")

                if r["recommendations"]:
                    with ui.card().classes("w-full"):
                        ui.label(f"{len(r['recommendations'])} Active Recommendation(s)").classes(
                            "font-semibold"
                        )
                        for rec in r["recommendations"]:
                            ui.label(f"• {rec['recommendation']} ({rec['severity']})").classes(
                                "text-sm text-gray-600"
                            )

        column_select.on("update:model-value", lambda: load_report())
        ui.timer(0.5, load_report, once=True)

ENCODING_METHODS = ["one_hot", "label", "ordinal", "frequency", "binary", "multi_label"]
SCALING_METHODS_LIST = ["standard", "minmax", "robust", "maxabs", "normalize"]


@ui.page("/encoding/{dataset_id}")
async def encoding_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Encoding Advisor").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        column_select = ui.select([], label="Column").classes("w-80")
        method_select = ui.select(ENCODING_METHODS, value="one_hot", label="Method").classes(
            "w-80"
        )
        order_input = ui.input(
            "Order (comma-separated, only for ordinal — e.g. Low,Medium,High)"
        ).classes("w-80")

        async def load_columns():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/column-types")
                if response.status_code == 200:
                    names = [
                        c["column"] for c in response.json()
                        if c["effective_type"] in ("categorical", "multi_label")
                    ]
                    column_select.set_options(names)
                    if names:
                        column_select.set_value(names[0])

        ui.timer(0.1, load_columns, once=True)

        async def do_encode():
            body = {"method": method_select.value}
            if method_select.value == "ordinal":
                body["order"] = [s.strip() for s in order_input.value.split(",") if s.strip()]

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/encode/apply",
                    json=body,
                )
                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        detail = f"Request failed ({response.status_code})"
                    ui.notify(detail, type="negative")
                    return
                overview = response.json()
            ui.notify(
                f"Encoded. Dataset now has {overview['columns']} columns.", type="positive"
            )

        ui.button("Apply Encoding", on_click=do_encode).props("color=positive")


@ui.page("/scaling/{dataset_id}")
async def scaling_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Scaling Advisor").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        column_select = ui.select([], label="Numeric Column").classes("w-80")
        method_select = ui.select(SCALING_METHODS_LIST, value="standard", label="Method").classes(
            "w-80"
        )

        async def load_numeric_columns():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/column-types")
                if response.status_code == 200:
                    names = [
                        c["column"] for c in response.json() if c["effective_type"] == "numerical"
                    ]
                    column_select.set_options(names)
                    if names:
                        column_select.set_value(names[0])

        ui.timer(0.1, load_numeric_columns, once=True)

        async def do_scale():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/datasets/{dataset_id}/columns/{column_select.value}/scale/apply",
                    json={"method": method_select.value},
                )
                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        detail = f"Request failed ({response.status_code})"
                    ui.notify(detail, type="negative")
                    return
            ui.notify("Scaling applied.", type="positive")

        ui.button("Apply Scaling", on_click=do_scale).props("color=positive")

@ui.page("/visualize/{dataset_id}")
async def visualize_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Visualization Center").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        all_columns = {"value": []}
        numeric_columns = {"value": []}
        categorical_columns = {"value": []}

        async def load_column_lists():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/column-types")
                if response.status_code == 200:
                    cols = response.json()
                    all_columns["value"] = [c["column"] for c in cols]
                    numeric_columns["value"] = [
                        c["column"] for c in cols if c["effective_type"] == "numerical"
                    ]
                    categorical_columns["value"] = [
                        c["column"] for c in cols if c["effective_type"] in ("categorical", "boolean")
                    ]

        await load_column_lists()

        with ui.tabs().classes("w-full") as tabs:
            scatter_tab = ui.tab("Scatter Plot")
            box_tab = ui.tab("Box Plot")
            bar_tab = ui.tab("Bar Chart")
            pie_tab = ui.tab("Pie Chart")

        with ui.tab_panels(tabs, value=scatter_tab).classes("w-full max-w-3xl"):

            with ui.tab_panel(scatter_tab):
                ui.label(
                    "When to use: exploring the relationship between two numeric variables. "
                    "What to observe: linear/non-linear trends, clusters, or outlier points."
                ).classes("text-xs text-gray-500 mb-2")
                with ui.row().classes("gap-2"):
                    x_select = ui.select(numeric_columns["value"], label="X axis").classes("w-60")
                    y_select = ui.select(numeric_columns["value"], label="Y axis").classes("w-60")
                scatter_container = ui.column().classes("w-full")

                async def load_scatter():
                    if not x_select.value or not y_select.value:
                        return
                    scatter_container.clear()
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.get(
                            f"{BACKEND_URL}/datasets/{dataset_id}/visualize/scatter",
                            params={"x_column": x_select.value, "y_column": y_select.value},
                        )
                    if response.status_code == 200:
                        data = response.json()
                        fig = go.Figure(
                            data=go.Scatter(
                                x=data["x_values"], y=data["y_values"], mode="markers",
                                marker=dict(size=5, opacity=0.6),
                            )
                        )
                        fig.update_layout(
                            xaxis_title=data["x_column"], yaxis_title=data["y_column"],
                            height=400, margin=dict(l=20, r=20, t=20, b=20),
                        )
                        with scatter_container:
                            ui.plotly(fig).classes("w-full")

                x_select.on("update:model-value", lambda: load_scatter())
                y_select.on("update:model-value", lambda: load_scatter())

            with ui.tab_panel(box_tab):
                ui.label(
                    "When to use: understanding spread and spotting outliers in a numeric column. "
                    "What to observe: box height (IQR), whisker length, and points beyond the whiskers."
                ).classes("text-xs text-gray-500 mb-2")
                box_select = ui.select(numeric_columns["value"], label="Column").classes("w-60")
                box_container = ui.column().classes("w-full")

                async def load_box():
                    if not box_select.value:
                        return
                    box_container.clear()
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.get(
                            f"{BACKEND_URL}/datasets/{dataset_id}/visualize/boxplot",
                            params={"column": box_select.value},
                        )
                    if response.status_code == 200:
                        data = response.json()
                        fig = go.Figure(data=go.Box(y=data["values"], name=data["column"]))
                        fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
                        with box_container:
                            ui.plotly(fig).classes("w-full")

                box_select.on("update:model-value", lambda: load_box())

            with ui.tab_panel(bar_tab):
                ui.label(
                    "When to use: comparing frequency across categories. "
                    "What to observe: which categories dominate, and whether any are rare."
                ).classes("text-xs text-gray-500 mb-2")
                bar_select = ui.select(categorical_columns["value"], label="Column").classes("w-60")
                bar_container = ui.column().classes("w-full")

                async def load_bar():
                    if not bar_select.value:
                        return
                    bar_container.clear()
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.get(
                            f"{BACKEND_URL}/datasets/{dataset_id}/columns/{bar_select.value}/category-frequencies"
                        )
                    if response.status_code == 200:
                        data = response.json()
                        fig = go.Figure(data=go.Bar(x=data["categories"], y=data["counts"]))
                        fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
                        with bar_container:
                            ui.plotly(fig).classes("w-full")

                bar_select.on("update:model-value", lambda: load_bar())

            with ui.tab_panel(pie_tab):
                ui.label(
                    "When to use: showing proportional share among a SMALL number of categories. "
                    "What to observe: relative size of each slice — avoid for high-cardinality columns."
                ).classes("text-xs text-gray-500 mb-2")
                pie_select = ui.select(categorical_columns["value"], label="Column").classes("w-60")
                pie_container = ui.column().classes("w-full")

                async def load_pie():
                    if not pie_select.value:
                        return
                    pie_container.clear()
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.get(
                            f"{BACKEND_URL}/datasets/{dataset_id}/columns/{pie_select.value}/category-frequencies"
                        )
                    if response.status_code == 200:
                        data = response.json()
                        fig = go.Figure(
                            data=go.Pie(labels=data["categories"], values=data["counts"])
                        )
                        fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
                        with pie_container:
                            ui.plotly(fig).classes("w-full")

                pie_select.on("update:model-value", lambda: load_pie())

@ui.page("/history/{dataset_id}")
async def history_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Version History").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        with ui.row().classes("gap-2"):
            undo_button = ui.button("↶ Undo")
            redo_button = ui.button("↷ Redo")

        history_container = ui.column().classes("w-full max-w-2xl gap-2")

        async def load_history():
            history_container.clear()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/history")
                if response.status_code != 200:
                    with history_container:
                        ui.label("❌ Could not load history.").classes("text-red-600")
                    return
                history = response.json()

            with history_container:
                for v in reversed(history["versions"]):  # newest first
                    with ui.card().classes(
                        "w-full " + ("border-2 border-blue-500" if v["is_current"] else "")
                    ):
                        with ui.row().classes("w-full items-center justify-between"):
                            with ui.column().classes("gap-0"):
                                ui.label(
                                    f"Version {v['version_num']}"
                                    + (" (current)" if v["is_current"] else "")
                                ).classes("font-semibold")
                                ui.label(v["description"]).classes("text-sm text-gray-600")
                                ui.label(v["timestamp"]).classes("text-xs text-gray-400")

                            if not v["is_current"]:
                                async def restore_version(version_num=v["version_num"]):
                                    async with httpx.AsyncClient(timeout=15.0) as client:
                                        response = await client.post(
                                            f"{BACKEND_URL}/datasets/{dataset_id}/restore/{version_num}"
                                        )
                                        if response.status_code != 200:
                                            try:
                                                detail = response.json().get("detail", "Unknown error")
                                            except Exception:
                                                detail = f"Request failed ({response.status_code})"
                                            ui.notify(detail, type="negative")
                                            return
                                    ui.notify(f"Restored to version {version_num}", type="positive")
                                    await load_history()

                                ui.button("Restore", on_click=restore_version).props("dense")

        async def do_undo():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(f"{BACKEND_URL}/datasets/{dataset_id}/undo")
                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        detail = f"Request failed ({response.status_code})"
                    ui.notify(detail, type="negative")
                    return
            ui.notify("Undone.", type="positive")
            await load_history()

        async def do_redo():
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(f"{BACKEND_URL}/datasets/{dataset_id}/redo")
                if response.status_code != 200:
                    try:
                        detail = response.json().get("detail", "Unknown error")
                    except Exception:
                        detail = f"Request failed ({response.status_code})"
                    ui.notify(detail, type="negative")
                    return
            ui.notify("Redone.", type="positive")
            await load_history()

        undo_button.on_click(do_undo)
        redo_button.on_click(do_redo)

        ui.timer(0.1, load_history, once=True)

@ui.page("/pipeline/{dataset_id}")
async def pipeline_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Pipeline").classes("text-2xl font-bold")
        ui.label(
            "Every transformation applied to this dataset, in order. "
            "Use the arrows to reorder — this re-runs every step from the original data."
        ).classes("text-sm text-gray-400 text-center max-w-xl")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        pipeline_container = ui.column().classes("w-full max-w-2xl gap-2")
        pipeline_state = {"steps": []}

        async def load_pipeline():
            pipeline_container.clear()
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{BACKEND_URL}/datasets/{dataset_id}/pipeline")
                if response.status_code != 200:
                    with pipeline_container:
                        ui.label("❌ Could not load pipeline.").classes("text-red-600")
                    return
                pipeline = response.json()

            pipeline_state["steps"] = pipeline["steps"]
            render_steps()

        def render_steps():
            pipeline_container.clear()
            steps = pipeline_state["steps"]

            if not steps:
                with pipeline_container:
                    ui.label(
                        "No transformations applied yet. Apply something from "
                        "Recommendations to see it appear here."
                    ).classes("text-sm text-gray-500")
                return

            with pipeline_container:
                for i, step in enumerate(steps):
                    with ui.card().classes("w-full"):
                        with ui.row().classes("items-center gap-3 justify-between w-full"):
                            with ui.row().classes("items-center gap-3"):
                                ui.label(f"{i + 1}").classes(
                                    "text-lg font-bold text-blue-600 w-6"
                                )
                                with ui.column().classes("gap-0"):
                                    ui.label(step["description"]).classes("font-semibold")
                                    if step["operation"]:
                                        ui.label(f"operation: {step['operation']}").classes(
                                            "text-xs text-gray-400"
                                        )

                            with ui.row().classes("gap-1"):
                                up_btn = ui.button(icon="arrow_upward").props(
                                    "flat dense round size=sm"
                                )
                                down_btn = ui.button(icon="arrow_downward").props(
                                    "flat dense round size=sm"
                                )
                                if i == 0:
                                    up_btn.disable()
                                if i == len(steps) - 1:
                                    down_btn.disable()

                                def move_up(index=i):
                                    steps[index], steps[index - 1] = steps[index - 1], steps[index]
                                    render_steps()

                                def move_down(index=i):
                                    steps[index], steps[index + 1] = steps[index + 1], steps[index]
                                    render_steps()

                                up_btn.on_click(move_up)
                                down_btn.on_click(move_down)

                async def apply_new_order():
                    version_order = [s["version_num"] for s in pipeline_state["steps"]]
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(
                            f"{BACKEND_URL}/datasets/{dataset_id}/pipeline/reorder",
                            json={"version_order": version_order},
                        )
                        if response.status_code != 200:
                            try:
                                detail = response.json().get("detail", "Unknown error")
                            except Exception:
                                detail = f"Request failed ({response.status_code})"
                            ui.notify(detail, type="negative", timeout=8000)
                            return
                    ui.notify("Pipeline reordered and re-applied.", type="positive")
                    await load_pipeline()

                ui.button("Apply New Order", on_click=apply_new_order).props(
                    "color=positive"
                ).classes("mt-2")

        ui.timer(0.1, load_pipeline, once=True)

@ui.page("/export/{dataset_id}")
async def export_page(dataset_id: str):
    with ui.column().classes("items-center w-full mt-10 gap-4"):
        ui.label("Export").classes("text-2xl font-bold")
        ui.link("← Back to recommendations", f"/recommendations/{dataset_id}").classes(
            "text-sm text-gray-400"
        )

        with ui.column().classes("w-full max-w-md gap-3"):
            with ui.card().classes("w-full"):
                ui.label("Processed Data").classes("font-semibold")
                ui.label("The current state of your dataset, ready for use elsewhere.").classes(
                    "text-sm text-gray-500 mb-2"
                )
                with ui.row().classes("gap-2"):
                    ui.button(
                        "Download CSV",
                        on_click=lambda: ui.navigate.to(
                            f"{BACKEND_URL}/datasets/{dataset_id}/export/csv", new_tab=True
                        ),
                    )
                    ui.button(
                        "Download Parquet",
                        on_click=lambda: ui.navigate.to(
                            f"{BACKEND_URL}/datasets/{dataset_id}/export/parquet", new_tab=True
                        ),
                    )

            with ui.card().classes("w-full"):
                ui.label("Pipeline Definition").classes("font-semibold")
                ui.label("Every transformation applied, as structured data.").classes(
                    "text-sm text-gray-500 mb-2"
                )
                with ui.row().classes("gap-2"):
                    ui.button(
                        "Download JSON",
                        on_click=lambda: ui.navigate.to(
                            f"{BACKEND_URL}/datasets/{dataset_id}/export/pipeline-json", new_tab=True
                        ),
                    )
                    ui.button(
                        "Download YAML",
                        on_click=lambda: ui.navigate.to(
                            f"{BACKEND_URL}/datasets/{dataset_id}/export/pipeline-yaml", new_tab=True
                        ),
                    )

            with ui.card().classes("w-full"):
                ui.label("Reproducible Python Script").classes("font-semibold")
                ui.label(
                    "A standalone .py file that reproduces your pipeline using plain "
                    "pandas/numpy/scipy — no dependency on this app."
                ).classes("text-sm text-gray-500 mb-2")
                ui.button(
                    "Download Script",
                    on_click=lambda: ui.navigate.to(
                        f"{BACKEND_URL}/datasets/{dataset_id}/export/pipeline-script", new_tab=True
                    ),
                ).props("color=positive")