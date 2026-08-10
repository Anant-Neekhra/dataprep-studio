import os

import httpx
from nicegui import ui
import plotly.graph_objects as go

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
        ui.link("View Recommendations →", f"/recommendations/{dataset_id}").classes(
            "text-sm text-blue-600"
        )

        table_container = ui.column().classes("w-full max-w-3xl gap-2")

        type_options = [
            "numerical", "categorical", "boolean", "datetime", "text", "id", "mixed"
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
        ui.link("Column Types & Drop Columns →", f"/column-types/{dataset_id}").classes(
            "text-sm text-blue-600"
        )

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

ui.run(title="DataPrep Studio", host="0.0.0.0", port=8080, reload=True)

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