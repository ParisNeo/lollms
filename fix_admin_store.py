
import re

path = "frontend/webui/src/stores/admin.js"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

# ---- 1. Replace the corrupted consumption-analytics functions -------------
# Anchor: from the (broken) `async exportConsumptionAnalytics(format) {`
# up to (but excluding) `async fetchDashboardStats() {`.
start_marker = "    async exportConsumptionAnalytics(format) {"
end_marker = "    async fetchDashboardStats() {"
start = src.find(start_marker)
end = src.find(end_marker)
if start == -1 or end == -1 or end <= start:
    raise SystemExit(f"Markers not found (start={start}, end={end})")

replacement = (
    "    async fetchConsumptionAnalytics(params = {}) {\n"
    "        try {\n"
    "            isLoadingConsumptionAnalytics.value = true;\n"
    "            const merged = { ...consumptionParams.value, ...params };\n"
    "            consumptionParams.value = merged;\n"
    "            const response = await api.get(`/admin/system/consumption-analytics`, {\n"
    "                params: {\n"
    "                    granularity: merged.granularity,\n"
    "                    source: merged.source,\n"
    "                    days: merged.days,\n"
    "                    top_n: merged.top_n ?? 10,\n"
    "                },\n"
    "            });\n"
    "            consumptionAnalytics.value = response.data;\n"
    "            return response.data;\n"
    "        } catch (error) {\n"
    "            console.error('Failed to fetch consumption analytics:', error);\n"
    "            consumptionAnalytics.value = null;\n"
    "            return null;\n"
    "        } finally {\n"
    "            isLoadingConsumptionAnalytics.value = false;\n"
    "        }\n"
    "    }\n"
    "\n"
    "    async exportConsumptionAnalytics(format = 'xlsx') {\n"
    "        const params = {\n"
    "            format,\n"
    "            granularity: consumptionParams.value.granularity,\n"
    "            source: consumptionParams.value.source,\n"
    "            days: consumptionParams.value.days,\n"
    "            top_n: consumptionParams.value.top_n ?? 10,\n"
    "        };\n"
    "        const response = await api.get(`/admin/system/consumption-analytics/export`, {\n"
    "            params,\n"
    "            responseType: 'blob',\n"
    "        });\n"
    "        const contentType = response.headers['content-type'] || 'application/octet-stream';\n"
    "        const blob = new Blob([response.data], { type: contentType });\n"
    "        const url = URL.createObjectURL(blob);\n"
    "        const a = document.createElement('a');\n"
    "        a.href = url;\n"
    "        const stamp = new Date().toISOString().slice(0, 10);\n"
    "        a.download = `token_consumption_${stamp}.${format}`;\n"
    "        document.body.appendChild(a);\n"
    "        a.click();\n"
    "        document.body.removeChild(a);\n"
    "        URL.revokeObjectURL(url);\n"
    "        return true;\n"
    "    }\n"
    "\n"
)

src = src[:start] + replacement + src[end:]

# ---- 2. Ensure the store exposes the new state + actions ------------------
# Find the LAST `return {` (the store's returned object) and verify our keys.
last_return = src.rfind("return {")
if last_return == -1:
    raise SystemExit("Store return block not found")

# Extract the return block substring up to the matching closing of the object.
# The store's return object normally ends with `};` before `});` or `}`.
tail = src[last_return:]

def ensure_key(tail_text, key, expr):
    # If key already listed, leave as-is; else inject after `return {`.
    if re.search(r"\b" + re.escape(key) + r"\b\s*[,:]", tail_text):
        return tail_text
    return tail_text.replace("return {", "return {\n        " + key + ": " + expr + ",", 1)

tail = ensure_key(tail, "consumptionAnalytics", "consumptionAnalytics")
tail = ensure_key(tail, "consumptionParams", "consumptionParams")
tail = ensure_key(tail, "isLoadingConsumptionAnalytics", "isLoadingConsumptionAnalytics")
tail = ensure_key(tail, "fetchConsumptionAnalytics", "fetchConsumptionAnalytics")
tail = ensure_key(tail, "exportConsumptionAnalytics", "exportConsumptionAnalytics")

src = src[:last_return] + tail

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

print("OK: store repaired. New length:", len(src.splitlines()))
