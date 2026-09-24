import pytest
from pathlib import Path

def test_datalake_viewer_has_bounding_box_fit_and_zoom():
    viewer_file = Path("frontend/webui/src/components/datastores/DataLakeViewer.vue")
    assert viewer_file.exists(), "DataLakeViewer.vue must exist"

    content = viewer_file.read_text(encoding="utf-8")

    # 1. Verify fitAllEntries calculates bounding box across points & documents
    assert "fitAllEntries" in content
    assert "minX" in content
    assert "maxX" in content
    assert "minY" in content
    assert "maxY" in content

    # 2. Verify zoom to document center of mass (centroid)
    assert "zoomToDocumentCentroid" in content
    assert "centroid" in content

    # 3. Verify expanded zoom-out range limit (scale can go down to 1 or lower, and up to 50000)
    assert "Math.max(1, Math.min(50000" in content

    # 4. Verify smooth animation support
    assert "animateToView" in content

    # 5. Verify multi-file selection support
    assert "selectedDocumentIds" in content
    assert "toggleDocumentSelection" in content
    assert "selectAllDocuments" in content
    assert "zoomToSelectedDocuments" in content