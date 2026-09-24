<script setup>
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import JsonRenderer from '../ui/JsonRenderer.vue';

const props = defineProps({
    store: { type: Object, required: true }
});

const emit = defineEmits(['view-document']);

const dataStore = useDataStore();
const uiStore = useUiStore();

const canvasRef = ref(null);
const isLoading = ref(false);
const dataLake = ref({ points: [], documents: [], total_chunks: 0, dimensions: 2, reduction_method: 'UMAP' });
const reductionMethod = ref('umap');
const dimensions = ref(2); // 2 or 3

const searchTerm = ref('');
const selectedDocumentIds = ref(new Set());
const activeDocumentFilter = computed({
    get: () => selectedDocumentIds.value.size === 1 ? Array.from(selectedDocumentIds.value)[0] : null,
    set: (val) => {
        if (!val) selectedDocumentIds.value = new Set();
        else selectedDocumentIds.value = new Set([val]);
    }
});
const selectedPoint = ref(null);
const hoveredPoint = ref(null);
const hoveredCentroid = ref(null);
const showCentroidSigns = ref(true);

// Document Viewer Modal State (invoked upon clicking a centroid sign)
const isDocViewerOpen = ref(false);
const viewingDoc = ref({
    name: '',
    color: '#3b82f6',
    symbol: 'star',
    chunkCount: 0,
    content: '',
    metadata: null,
    isLoading: false,
    error: null
});

// Viewport / Camera State
const transform = ref({ x: 0, y: 0, scale: 1 });
const camera3D = ref({ pitch: -0.35, yaw: 0.55 });
const isDragging = ref(false);
const isPanning3D = ref(false);
const dragStart = ref({ x: 0, y: 0 });
let animFrameId = null;

const filteredPoints = computed(() => {
    let list = dataLake.value.points || [];
    if (selectedDocumentIds.value.size > 0) {
        list = list.filter(p => selectedDocumentIds.value.has(p.document_id));
    }
    if (searchTerm.value.trim()) {
        const query = searchTerm.value.toLowerCase().trim();
        list = list.filter(p => 
            p.document_name.toLowerCase().includes(query) ||
            p.full_text.toLowerCase().includes(query)
        );
    }
    return list;
});

const filteredCentroids = computed(() => {
    let list = dataLake.value.documents || [];
    if (selectedDocumentIds.value.size > 0) {
        list = list.filter(d => selectedDocumentIds.value.has(d.id));
    }
    return list;
});

async function loadDataLake() {
    if (!props.store?.id) return;
    isLoading.value = true;
    try {
        const res = await dataStore.fetchDataLakeData(props.store.id, reductionMethod.value, dimensions.value);
        dataLake.value = res || { points: [], documents: [], total_chunks: 0, dimensions: dimensions.value, reduction_method: reductionMethod.value.toUpperCase() };
    } catch (e) {
        console.error("Failed to load data lake:", e);
        uiStore.addNotification("Could not load embedding data lake.", "error");
    } finally {
        isLoading.value = false;
        nextTick(() => {
            fitAllEntries(false);
        });
    }
}

// ── Smooth Animation Engine ──
function cancelAnimation() {
    if (animFrameId) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
    }
}

function animateToView(targetTransform, duration = 380) {
    cancelAnimation();
    const startX = transform.value.x;
    const startY = transform.value.y;
    const startScale = transform.value.scale;
    const startTime = performance.now();

    function step(now) {
        const elapsed = now - startTime;
        const progress = Math.min(1, elapsed / duration);
        const ease = 1 - Math.pow(1 - progress, 3); // easeOutCubic

        transform.value.x = startX + (targetTransform.x - startX) * ease;
        transform.value.y = startY + (targetTransform.y - startY) * ease;
        transform.value.scale = startScale + (targetTransform.scale - startScale) * ease;

        renderCanvas();

        if (progress < 1) {
            animFrameId = requestAnimationFrame(step);
        } else {
            animFrameId = null;
        }
    }
    animFrameId = requestAnimationFrame(step);
}

// ── Projection Mathematics ──
function getProjectedOffset(x, y, z = 0) {
    if (dimensions.value === 2) {
        return { projX: x, projY: y };
    }
    const { pitch, yaw } = camera3D.value;
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const x1 = x * cosY - z * sinY;
    const z1 = x * sinY + z * cosY;

    const cosP = Math.cos(pitch);
    const sinP = Math.sin(pitch);
    const y2 = y * cosP - z1 * sinP;
    const z2 = y * sinP + z1 * cosP;
    const x2 = x1;

    const cameraDist = 4.0;
    const persp = cameraDist / Math.max(0.1, cameraDist + z2 * 0.85);

    return {
        projX: x2 * persp,
        projY: y2 * persp
    };
}

function projectPoint(x, y, z = 0) {
    const { x: cx, y: cy, scale } = transform.value;

    if (dimensions.value === 2) {
        return {
            screenX: cx + x * scale,
            screenY: cy + y * scale,
            depth: 0,
            persp: 1
        };
    }

    const { pitch, yaw } = camera3D.value;
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const x1 = x * cosY - z * sinY;
    const z1 = x * sinY + z * cosY;

    const cosP = Math.cos(pitch);
    const sinP = Math.sin(pitch);
    const y2 = y * cosP - z1 * sinP;
    const z2 = y * sinP + z1 * cosP;
    const x2 = x1;

    const cameraDist = 4.0;
    const persp = cameraDist / Math.max(0.1, cameraDist + z2 * 0.85);

    return {
        screenX: cx + x2 * scale * persp,
        screenY: cy + y2 * scale * persp,
        depth: z2,
        persp
    };
}

// ── Zoom-Out To Cover All Entries (2D & 3D) ──
function fitAllEntries(animate = false) {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const W = rect.width;
    const H = rect.height;

    if (W === 0 || H === 0) {
        requestAnimationFrame(() => fitAllEntries(animate));
        return;
    }

    const points = dataLake.value.points || [];
    const docs = dataLake.value.documents || [];

    if (points.length === 0 && docs.length === 0) {
        const fallback = {
            x: W / 2,
            y: H / 2,
            scale: Math.min(W, H) * (dimensions.value === 3 ? 0.38 : 0.42)
        };
        if (animate) animateToView(fallback);
        else {
            transform.value = fallback;
            renderCanvas();
        }
        return;
    }

    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;

    for (let i = 0; i < points.length; i++) {
        const p = points[i];
        const { projX, projY } = getProjectedOffset(p.x, p.y, p.z || 0);
        if (projX < minX) minX = projX;
        if (projX > maxX) maxX = projX;
        if (projY < minY) minY = projY;
        if (projY > maxY) maxY = projY;
    }

    for (let i = 0; i < docs.length; i++) {
        const d = docs[i];
        if (d.centroid) {
            const cz = d.centroid.z !== undefined ? d.centroid.z : 0;
            const { projX, projY } = getProjectedOffset(d.centroid.x, d.centroid.y, cz);
            if (projX < minX) minX = projX;
            if (projX > maxX) maxX = projX;
            if (projY < minY) minY = projY;
            if (projY > maxY) maxY = projY;
        }
    }

    const spanX = Math.max(0.001, maxX - minX);
    const spanY = Math.max(0.001, maxY - minY);
    const midX = (minX + maxX) / 2;
    const midY = (minY + maxY) / 2;

    const padding = Math.max(40, Math.min(W, H) * 0.12);
    const availW = Math.max(40, W - padding * 2);
    const availH = Math.max(40, H - padding * 2);

    const fitScale = Math.min(availW / spanX, availH / spanY);
    const targetScale = Math.max(1, Math.min(50000, fitScale));

    const targetX = W / 2 - midX * targetScale;
    const targetY = H / 2 - midY * targetScale;

    if (animate) {
        animateToView({ x: targetX, y: targetY, scale: targetScale });
    } else {
        transform.value = { x: targetX, y: targetY, scale: targetScale };
        renderCanvas();
    }
}

// ── Zoom In on Document Center of Mass (Centroid) ──
function zoomToDocumentCentroid(docId, animate = true) {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const W = rect.width;
    const H = rect.height;
    if (W === 0 || H === 0) return;

    const doc = (dataLake.value.documents || []).find(d => d.id === docId);
    if (!doc || !doc.centroid) return;

    const cz = doc.centroid.z !== undefined ? doc.centroid.z : 0;
    const { projX: cProjX, projY: cProjY } = getProjectedOffset(doc.centroid.x, doc.centroid.y, cz);

    const docPoints = (dataLake.value.points || []).filter(p => p.document_id === docId);

    let targetScale;
    if (docPoints.length > 1) {
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;

        for (const p of docPoints) {
            const { projX, projY } = getProjectedOffset(p.x, p.y, p.z || 0);
            if (projX < minX) minX = projX;
            if (projX > maxX) maxX = projX;
            if (projY < minY) minY = projY;
            if (projY > maxY) maxY = projY;
        }

        const spanX = Math.max(0.005, maxX - minX);
        const spanY = Math.max(0.005, maxY - minY);
        const padding = Math.max(50, Math.min(W, H) * 0.2);
        const availW = Math.max(50, W - padding * 2);
        const availH = Math.max(50, H - padding * 2);

        const fitScale = Math.min(availW / spanX, availH / spanY);
        targetScale = Math.max(5, Math.min(8000, fitScale));
    } else {
        targetScale = Math.max(transform.value.scale * 1.8, Math.min(W, H) * 0.9);
    }

    const targetX = W / 2 - cProjX * targetScale;
    const targetY = H / 2 - cProjY * targetScale;

    if (animate) {
        animateToView({ x: targetX, y: targetY, scale: targetScale }, 420);
    } else {
        transform.value = { x: targetX, y: targetY, scale: targetScale };
        renderCanvas();
    }
}

function zoomToSelectedDocuments(animate = true) {
    if (selectedDocumentIds.value.size === 1) {
        const singleId = Array.from(selectedDocumentIds.value)[0];
        zoomToDocumentCentroid(singleId, animate);
        return;
    }
    const canvas = canvasRef.value;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const W = rect.width;
    const H = rect.height;
    if (W === 0 || H === 0) return;

    const docIds = selectedDocumentIds.value;
    const docPoints = (dataLake.value.points || []).filter(p => docIds.has(p.document_id));

    if (docPoints.length === 0) {
        fitAllEntries(animate);
        return;
    }

    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;

    for (const p of docPoints) {
        const { projX, projY } = getProjectedOffset(p.x, p.y, p.z || 0);
        if (projX < minX) minX = projX;
        if (projX > maxX) maxX = projX;
        if (projY < minY) minY = projY;
        if (projY > maxY) maxY = projY;
    }

    const spanX = Math.max(0.005, maxX - minX);
    const spanY = Math.max(0.005, maxY - minY);
    const padding = Math.max(50, Math.min(W, H) * 0.18);
    const availW = Math.max(50, W - padding * 2);
    const availH = Math.max(50, H - padding * 2);

    const fitScale = Math.min(availW / spanX, availH / spanY);
    const targetScale = Math.max(5, Math.min(10000, fitScale));

    const midX = (minX + maxX) / 2;
    const midY = (minY + maxY) / 2;

    const targetX = W / 2 - midX * targetScale;
    const targetY = H / 2 - midY * targetScale;

    if (animate) {
        animateToView({ x: targetX, y: targetY, scale: targetScale }, 420);
    } else {
        transform.value = { x: targetX, y: targetY, scale: targetScale };
        renderCanvas();
    }
}

function resetView() {
    fitAllEntries(true);
}

// ── Centroid Geometric Signs Drawing Engine ──
function drawCentroidShape(ctx, x, y, size, shape, color, isHovered, isSelected) {
    ctx.save();
    ctx.fillStyle = color;
    ctx.strokeStyle = isHovered ? '#ffffff' : (uiStore.currentTheme === 'dark' ? '#0f172a' : '#ffffff');
    ctx.lineWidth = isHovered ? 2.5 : 1.5;
    ctx.shadowColor = color;
    ctx.shadowBlur = isHovered ? 14 : (isSelected ? 10 : 4);

    const r = size;
    ctx.beginPath();

    switch (shape) {
        case 'star': {
            const spikes = 5;
            const outerR = r * 1.15;
            const innerR = r * 0.5;
            let rot = (Math.PI / 2) * 3;
            const step = Math.PI / spikes;
            ctx.moveTo(x, y - outerR);
            for (let i = 0; i < spikes; i++) {
                ctx.lineTo(x + Math.cos(rot) * outerR, y + Math.sin(rot) * outerR);
                rot += step;
                ctx.lineTo(x + Math.cos(rot) * innerR, y + Math.sin(rot) * innerR);
                rot += step;
            }
            ctx.closePath();
            break;
        }
        case 'diamond': {
            ctx.moveTo(x, y - r * 1.25);
            ctx.lineTo(x + r * 1.25, y);
            ctx.lineTo(x, y + r * 1.25);
            ctx.lineTo(x - r * 1.25, y);
            ctx.closePath();
            break;
        }
        case 'triangle_up': {
            ctx.moveTo(x, y - r * 1.3);
            ctx.lineTo(x + r * 1.15, y + r * 0.85);
            ctx.lineTo(x - r * 1.15, y + r * 0.85);
            ctx.closePath();
            break;
        }
        case 'triangle_down': {
            ctx.moveTo(x, y + r * 1.3);
            ctx.lineTo(x + r * 1.15, y - r * 0.85);
            ctx.lineTo(x - r * 1.15, y - r * 0.85);
            ctx.closePath();
            break;
        }
        case 'square': {
            const side = r * 1.8;
            ctx.rect(x - side / 2, y - side / 2, side, side);
            break;
        }
        case 'cross': {
            const w = r * 0.45;
            const len = r * 1.3;
            ctx.save();
            ctx.translate(x, y);
            ctx.rotate(Math.PI / 4);
            ctx.rect(-w / 2, -len, w, len * 2);
            ctx.rect(-len, -w / 2, len * 2, w);
            ctx.restore();
            break;
        }
        case 'plus': {
            const w = r * 0.45;
            const len = r * 1.3;
            ctx.rect(x - w / 2, y - len, w, len * 2);
            ctx.rect(x - len, y - w / 2, len * 2, w);
            break;
        }
        case 'hexagon': {
            for (let i = 0; i < 6; i++) {
                const angle = (i * Math.PI) / 3;
                const hx = x + r * 1.15 * Math.cos(angle);
                const hy = y + r * 1.15 * Math.sin(angle);
                if (i === 0) ctx.moveTo(hx, hy);
                else ctx.lineTo(hx, hy);
            }
            ctx.closePath();
            break;
        }
        case 'pentagon': {
            for (let i = 0; i < 5; i++) {
                const angle = (i * 2 * Math.PI) / 5 - Math.PI / 2;
                const px = x + r * 1.15 * Math.cos(angle);
                const py = y + r * 1.15 * Math.sin(angle);
                if (i === 0) ctx.moveTo(px, py);
                else ctx.lineTo(px, py);
            }
            ctx.closePath();
            break;
        }
        case 'circle_cross': {
            ctx.arc(x, y, r, 0, Math.PI * 2);
            ctx.moveTo(x - r, y);
            ctx.lineTo(x + r, y);
            ctx.moveTo(x, y - r);
            ctx.lineTo(x, y + r);
            break;
        }
        default: {
            ctx.moveTo(x, y - r * 1.2);
            ctx.lineTo(x + r * 1.2, y);
            ctx.lineTo(x, y + r * 1.2);
            ctx.lineTo(x - r * 1.2, y);
            ctx.closePath();
            break;
        }
    }

    ctx.fill();
    ctx.stroke();

    if (isHovered) {
        ctx.beginPath();
        ctx.arc(x, y, r * 0.35, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
    }

    ctx.restore();
}

function renderCanvas() {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    if (canvas.width !== rect.width * dpr || canvas.height !== rect.height * dpr) {
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
    }

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const isDark = uiStore.currentTheme === 'dark';
    const is3D = dimensions.value === 3;
    const { x: cx, y: cy, scale } = transform.value;

    // ── 1. Reference Plane / Axes ──
    if (is3D) {
        ctx.strokeStyle = isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)';
        ctx.lineWidth = 1;
        const gridStep = 0.5;
        const gridRange = 1.5;

        for (let gx = -gridRange; gx <= gridRange; gx += gridStep) {
            const p1 = projectPoint(gx, 0.8, -gridRange);
            const p2 = projectPoint(gx, 0.8, gridRange);
            ctx.beginPath();
            ctx.moveTo(p1.screenX, p1.screenY);
            ctx.lineTo(p2.screenX, p2.screenY);
            ctx.stroke();
        }
        for (let gz = -gridRange; gz <= gridRange; gz += gridStep) {
            const p1 = projectPoint(-gridRange, 0.8, gz);
            const p2 = projectPoint(gridRange, 0.8, gz);
            ctx.beginPath();
            ctx.moveTo(p1.screenX, p1.screenY);
            ctx.lineTo(p2.screenX, p2.screenY);
            ctx.stroke();
        }

        const origin = projectPoint(0, 0, 0);
        const axisX = projectPoint(0.4, 0, 0);
        const axisY = projectPoint(0, -0.4, 0);
        const axisZ = projectPoint(0, 0, 0.4);

        ctx.lineWidth = 1.5;
        ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)';
        ctx.beginPath(); ctx.moveTo(origin.screenX, origin.screenY); ctx.lineTo(axisX.screenX, axisX.screenY); ctx.stroke();
        ctx.strokeStyle = 'rgba(34, 197, 94, 0.4)';
        ctx.beginPath(); ctx.moveTo(origin.screenX, origin.screenY); ctx.lineTo(axisY.screenX, axisY.screenY); ctx.stroke();
        ctx.strokeStyle = 'rgba(59, 130, 246, 0.4)';
        ctx.beginPath(); ctx.moveTo(origin.screenX, origin.screenY); ctx.lineTo(axisZ.screenX, axisZ.screenY); ctx.stroke();
    } else {
        ctx.strokeStyle = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, cy); ctx.lineTo(rect.width, cy);
        ctx.moveTo(cx, 0); ctx.lineTo(cx, rect.height);
        ctx.stroke();

        for (let r = 0.25; r <= 1.0; r += 0.25) {
            ctx.beginPath();
            ctx.arc(cx, cy, r * scale, 0, Math.PI * 2);
            ctx.stroke();
        }
    }

    // ── 2. Unified Depth Sorting for 3D ──
    const renderItems = [];

    filteredPoints.value.forEach(p => {
        const proj = projectPoint(p.x, p.y, p.z || 0);
        renderItems.push({
            kind: 'chunk',
            point: p,
            screenX: proj.screenX,
            screenY: proj.screenY,
            depth: proj.depth,
            persp: proj.persp
        });
    });

    if (showCentroidSigns.value) {
        filteredCentroids.value.forEach(doc => {
            const cz = doc.centroid.z !== undefined ? doc.centroid.z : 0;
            const proj = projectPoint(doc.centroid.x, doc.centroid.y, cz);
            renderItems.push({
                kind: 'centroid',
                doc,
                screenX: proj.screenX,
                screenY: proj.screenY,
                depth: proj.depth - 0.01,
                persp: proj.persp
            });
        });
    }

    if (is3D) {
        renderItems.sort((a, b) => a.depth - b.depth);
    }

    // ── 3. Render Inactive Ghost Points if Filter is Active ──
    if (selectedDocumentIds.value.size > 0 || searchTerm.value.trim()) {
        const allPoints = dataLake.value.points || [];
        ctx.fillStyle = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.04)';
        allPoints.forEach(p => {
            if (selectedDocumentIds.value.size > 0 && selectedDocumentIds.value.has(p.document_id)) return;
            const proj = projectPoint(p.x, p.y, p.z || 0);
            ctx.beginPath();
            ctx.arc(proj.screenX, proj.screenY, 2.5, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    // ── 4. Render Active Elements ──
    renderItems.forEach(item => {
        if (item.kind === 'chunk') {
            const p = item.point;
            const isHovered = hoveredPoint.value?.id === p.id;
            const isSelected = selectedPoint.value?.id === p.id;
            const baseR = isSelected ? 8 : (isHovered ? 6.5 : 4);
            const radius = Math.max(2, baseR * (is3D ? item.persp : 1));

            if (isHovered || isSelected) {
                ctx.beginPath();
                ctx.arc(item.screenX, item.screenY, radius + 3, 0, Math.PI * 2);
                ctx.fillStyle = isSelected ? 'rgba(59, 130, 246, 0.35)' : 'rgba(255, 255, 255, 0.25)';
                ctx.fill();
            }

            ctx.beginPath();
            ctx.arc(item.screenX, item.screenY, radius, 0, Math.PI * 2);
            ctx.fillStyle = p.color;
            ctx.fill();
            ctx.lineWidth = isSelected ? 2 : 0.8;
            ctx.strokeStyle = isSelected ? '#ffffff' : (isDark ? '#0f172a' : '#ffffff');
            ctx.stroke();
        } else if (item.kind === 'centroid') {
            const doc = item.doc;
            const isHovered = hoveredCentroid.value?.id === doc.id;
            const isSelected = selectedDocumentIds.value.has(doc.id);
            const baseSize = isHovered ? 11 : 8.5;
            const size = Math.max(4.5, baseSize * (is3D ? item.persp : 1));

            drawCentroidShape(
                ctx,
                item.screenX,
                item.screenY,
                size,
                doc.symbol || 'star',
                doc.color,
                isHovered,
                isSelected
            );
        }
    });

    ctx.restore();
}

// ── Interaction: Mouse Handlers (Orbit 3D & Pan 2D) ──
function handleMouseDown(e) {
    cancelAnimation();
    isDragging.value = true;
    dragStart.value = { x: e.clientX, y: e.clientY };
    isPanning3D.value = e.shiftKey || e.button === 1 || e.button === 2;
}

function handleMouseMove(e) {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (isDragging.value) {
        const dx = e.clientX - dragStart.value.x;
        const dy = e.clientY - dragStart.value.y;

        if (dimensions.value === 3 && !isPanning3D.value) {
            camera3D.value.yaw += dx * 0.007;
            camera3D.value.pitch = Math.max(-1.45, Math.min(1.45, camera3D.value.pitch + dy * 0.007));
        } else {
            transform.value.x += dx;
            transform.value.y += dy;
        }

        dragStart.value = { x: e.clientX, y: e.clientY };
        renderCanvas();
        return;
    }

    let matchedCentroid = null;
    if (showCentroidSigns.value) {
        for (const doc of filteredCentroids.value) {
            const cz = doc.centroid.z !== undefined ? doc.centroid.z : 0;
            const proj = projectPoint(doc.centroid.x, doc.centroid.y, cz);
            const dist = Math.hypot(proj.screenX - mouseX, proj.screenY - mouseY);
            if (dist <= 14) {
                matchedCentroid = { ...doc, screenX: proj.screenX, screenY: proj.screenY };
                break;
            }
        }
    }

    let matchedPoint = null;
    if (!matchedCentroid) {
        let minDist = 11;
        for (const p of filteredPoints.value) {
            const proj = projectPoint(p.x, p.y, p.z || 0);
            const dist = Math.hypot(proj.screenX - mouseX, proj.screenY - mouseY);
            if (dist < minDist) {
                minDist = dist;
                matchedPoint = { ...p, screenX: proj.screenX, screenY: proj.screenY };
            }
        }
    }

    let needsRender = false;
    if (hoveredCentroid.value?.id !== matchedCentroid?.id) {
        hoveredCentroid.value = matchedCentroid;
        needsRender = true;
    }
    if (hoveredPoint.value?.id !== matchedPoint?.id) {
        hoveredPoint.value = matchedPoint;
        needsRender = true;
    }
    if (needsRender) {
        renderCanvas();
    }
}

function handleMouseUp() {
    isDragging.value = false;
    isPanning3D.value = false;
}

async function handleClick() {
    if (hoveredCentroid.value) {
        toggleDocumentSelection(hoveredCentroid.value.id, true);
        return;
    }

    if (hoveredPoint.value) {
        selectedPoint.value = hoveredPoint.value;
    } else {
        selectedPoint.value = null;
    }
    renderCanvas();
}

function handleWheel(e) {
    e.preventDefault();
    cancelAnimation();
    const canvas = canvasRef.value;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    // Allow zooming out further (scale down to 1) and in up to 50000
    const newScale = Math.max(1, Math.min(50000, transform.value.scale * zoomFactor));

    transform.value.x = mouseX - (mouseX - transform.value.x) * (newScale / transform.value.scale);
    transform.value.y = mouseY - (mouseY - transform.value.y) * (newScale / transform.value.scale);
    transform.value.scale = newScale;

    renderCanvas();
}

// ── Document Viewer Execution (Click Centroid) ──
async function viewDocument(doc) {
    if (!doc || !props.store?.id) return;

    viewingDoc.value = {
        name: doc.name,
        color: doc.color,
        symbol: doc.symbol || 'star',
        chunkCount: doc.chunk_count,
        content: '',
        metadata: null,
        isLoading: true,
        error: null
    };
    isDocViewerOpen.value = true;

    emit('view-document', { filename: doc.name });

    try {
        const res = await dataStore.fetchFileContent(props.store.id, doc.name);
        viewingDoc.value.content = res || 'No text content could be reconstructed for this document.';
    } catch (e) {
        console.error("Failed to load document content:", e);
        viewingDoc.value.error = "Failed to load document content from SafeStore.";
        uiStore.addNotification(`Could not load content for '${doc.name}'.`, 'error');
    } finally {
        viewingDoc.value.isLoading = false;
    }
}

function downloadCurrentDocument() {
    if (!viewingDoc.value.content) return;
    const blob = new Blob([viewingDoc.value.content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = viewingDoc.value.name.endsWith('.md') ? viewingDoc.value.name : `${viewingDoc.value.name}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function isDocumentSelected(docId) {
    return selectedDocumentIds.value.has(docId);
}

function toggleDocumentSelection(docId, autoZoom = true) {
    if (selectedDocumentIds.value.has(docId)) {
        selectedDocumentIds.value.delete(docId);
    } else {
        selectedDocumentIds.value.add(docId);
    }
    selectedDocumentIds.value = new Set(selectedDocumentIds.value);

    if (autoZoom) {
        if (selectedDocumentIds.value.size > 0) {
            zoomToSelectedDocuments(true);
        } else {
            fitAllEntries(true);
        }
    }
    renderCanvas();
}

function selectAllDocuments() {
    const allDocIds = (dataLake.value.documents || []).map(d => d.id);
    selectedDocumentIds.value = new Set(allDocIds);
    fitAllEntries(true);
    renderCanvas();
}

function clearDocumentFilter() {
    selectedDocumentIds.value = new Set();
    fitAllEntries(true);
    renderCanvas();
}

function soloDocument(docId) {
    if (selectedDocumentIds.value.size === 1 && selectedDocumentIds.value.has(docId)) {
        clearDocumentFilter();
    } else {
        selectedDocumentIds.value = new Set([docId]);
        zoomToDocumentCentroid(docId, true);
    }
    renderCanvas();
}

function toggleDocumentSolo(docId) {
    soloDocument(docId);
}

function openStandaloneVisualizer() {
    if (!props.store?.id) return;
    const url = `/api/store/${props.store.id}/data-lake/export-html?method=${reductionMethod.value}&dimensions=${dimensions.value}`;
    window.open(url, '_blank');
}

function copyText(text) {
    navigator.clipboard.writeText(text);
    uiStore.addNotification("Copied to clipboard.", "success");
}

function getShapeGlyph(shape) {
    switch (shape) {
        case 'star': return '★';
        case 'diamond': return '◆';
        case 'triangle_up': return '▲';
        case 'triangle_down': return '▼';
        case 'square': return '■';
        case 'cross': return '✕';
        case 'plus': return '✚';
        case 'hexagon': return '⬢';
        case 'circle_cross': return '⊕';
        case 'pentagon': return '⬟';
        default: return '◆';
    }
}

watch([reductionMethod, dimensions, () => props.store?.id], () => {
    loadDataLake();
});

watch([searchTerm, showCentroidSigns], () => {
    renderCanvas();
});

watch(() => uiStore.currentTheme, () => {
    nextTick(() => renderCanvas());
});

onMounted(() => {
    loadDataLake();
    window.addEventListener('resize', renderCanvas);
});

onUnmounted(() => {
    cancelAnimation();
    window.removeEventListener('resize', renderCanvas);
});
</script>

<template>
    <div class="h-full flex flex-col overflow-hidden bg-white dark:bg-gray-950 relative select-none">
        
        <!-- Header Toolbar -->
        <header class="px-5 py-3 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex flex-wrap items-center justify-between gap-3 shrink-0 z-20">
            <div class="flex items-center gap-3 flex-wrap">
                <!-- Reduction Method Selector (UMAP, PCA, t-SNE) -->
                <div class="flex items-center gap-1.5">
                    <span class="text-xs font-black uppercase text-gray-500 tracking-wider">Projection:</span>
                    <select v-model="reductionMethod" class="input-field !py-1 !px-2.5 text-xs font-bold bg-white dark:bg-gray-800">
                        <option value="umap">UMAP (Cosine Manifold - SOTA)</option>
                        <option value="pca">PCA (Fast SVD)</option>
                        <option value="tsne">t-SNE (Clustering)</option>
                    </select>
                </div>

                <div class="h-4 w-px bg-gray-300 dark:bg-gray-700 hidden sm:block"></div>

                <!-- 2D / 3D Dimensionality Toggle -->
                <div class="flex items-center rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 p-0.5 text-xs font-bold">
                    <button 
                        type="button" 
                        @click="dimensions = 2" 
                        class="px-3 py-1 rounded-lg transition-all flex items-center gap-1 cursor-pointer select-none"
                        :class="dimensions === 2 ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-xs font-black' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'"
                    >
                        <span>2D Space</span>
                    </button>
                    <button 
                        type="button" 
                        @click="dimensions = 3" 
                        class="px-3 py-1 rounded-lg transition-all flex items-center gap-1 cursor-pointer select-none"
                        :class="dimensions === 3 ? 'bg-white dark:bg-gray-700 text-purple-600 dark:text-purple-400 shadow-xs font-black' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'"
                    >
                        <span>3D Cloud</span>
                    </button>
                </div>

                <div class="h-4 w-px bg-gray-300 dark:bg-gray-700 hidden sm:block"></div>

                <!-- Centroid Signs Toggle -->
                <label class="flex items-center gap-1.5 text-xs font-bold text-gray-600 dark:text-gray-300 cursor-pointer select-none">
                    <input type="checkbox" v-model="showCentroidSigns" class="rounded text-purple-600 focus:ring-purple-500 w-3.5 h-3.5">
                    <span>Centers of Gravity</span>
                </label>
            </div>

            <!-- Search Field -->
            <div class="flex items-center gap-2 grow max-w-xs">
                <div class="relative w-full">
                    <input 
                        type="text" 
                        v-model="searchTerm" 
                        placeholder="Search text in datalake..." 
                        class="input-field !py-1 !pl-8 !pr-7 text-xs w-full bg-white dark:bg-gray-800"
                    />
                    <IconMagnifyingGlass class="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                    <button v-if="searchTerm" @click="searchTerm = ''" class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                        <IconXMark class="w-3 h-3" />
                    </button>
                </div>
            </div>

            <!-- Action Controls -->
            <div class="flex items-center gap-2">
                <button @click="openStandaloneVisualizer" class="btn btn-secondary btn-sm h-8 flex items-center gap-1.5 text-blue-600 dark:text-blue-400" title="Open Standalone Interactive HTML Visualizer">
                    <IconGlobeAlt class="w-3.5 h-3.5" />
                    <span class="hidden sm:inline">Export HTML</span>
                </button>
                <button @click="loadDataLake" class="btn btn-secondary btn-sm h-8" title="Recompute Embedding Projection">
                    <IconRefresh class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
                    <span class="hidden sm:inline">Refresh</span>
                </button>
                <button @click="resetView" class="btn btn-secondary btn-sm h-8" title="Reset View / Fit All Entries">
                    <IconMaximize class="w-3.5 h-3.5" />
                    <span>Fit</span>
                </button>
            </div>
        </header>

        <!-- Main Workspace Viewport -->
        <div class="grow flex flex-row overflow-hidden relative">
            <div 
                class="grow h-full relative overflow-hidden"
                :class="hoveredCentroid ? 'cursor-pointer' : (dimensions === 3 ? (isDragging ? 'cursor-grabbing' : 'cursor-grab') : 'cursor-crosshair')"
            >
                <canvas 
                    ref="canvasRef"
                    class="absolute inset-0 w-full h-full"
                    @mousedown="handleMouseDown"
                    @mousemove="handleMouseMove"
                    @mouseup="handleMouseUp"
                    @click="handleClick"
                    @wheel="handleWheel"
                    @contextmenu.prevent
                ></canvas>

                <!-- Centroid Hover Tooltip -->
                <div 
                    v-if="hoveredCentroid && !isDragging"
                    class="absolute pointer-events-none z-30 bg-white/95 dark:bg-gray-900/95 backdrop-blur-md px-3.5 py-2.5 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-800 max-w-sm transition-opacity duration-150 animate-in fade-in"
                    :style="{ left: hoveredCentroid.screenX + 'px', top: hoveredCentroid.screenY + 'px', transform: 'translate(-50%, -125%)' }"
                >
                    <div class="flex items-center gap-2 pb-1 border-b dark:border-gray-800">
                        <span class="text-sm font-bold" :style="{ color: hoveredCentroid.color }">
                            {{ getShapeGlyph(hoveredCentroid.symbol) }}
                        </span>
                        <span class="font-bold text-xs truncate text-gray-900 dark:text-white">{{ hoveredCentroid.name }}</span>
                    </div>
                    <div class="flex items-center justify-between gap-4 mt-1.5 text-[10px]">
                        <span class="text-gray-500 font-mono">{{ hoveredCentroid.chunk_count }} Chunks (Center of Gravity)</span>
                        <span class="font-bold text-purple-600 dark:text-purple-400 uppercase tracking-wider">
                            {{ isDocumentSelected(hoveredCentroid.id) ? 'Selected (Click to deselect)' : 'Click to select' }}
                        </span>
                    </div>
                </div>

                <!-- Chunk Point Hover Tooltip -->
                <div 
                    v-else-if="hoveredPoint && !isDragging"
                    class="absolute pointer-events-none z-30 bg-white/95 dark:bg-gray-900/95 backdrop-blur-md p-3.5 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-800 max-w-xs transition-opacity duration-150"
                    :style="{ left: hoveredPoint.screenX + 'px', top: hoveredPoint.screenY + 'px', transform: 'translate(-50%, -120%)' }"
                >
                    <div class="flex items-center gap-2 pb-1.5 border-b dark:border-gray-800 mb-2">
                        <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: hoveredPoint.color }"></span>
                        <span class="font-bold text-xs truncate text-gray-900 dark:text-white">{{ hoveredPoint.document_name }}</span>
                        <span class="text-[9px] font-mono text-gray-400">#{{ hoveredPoint.chunk_index }}</span>
                    </div>
                    <p class="text-[11px] text-gray-600 dark:text-gray-300 line-clamp-3 leading-relaxed italic">
                        "{{ hoveredPoint.text_snippet }}"
                    </p>
                    <span class="block mt-2 text-[9px] font-bold text-blue-500 uppercase tracking-wider">Click to Inspect Chunk</span>
                </div>

                <!-- 3D Navigation Guide Pill -->
                <div v-if="dimensions === 3" class="absolute bottom-4 left-4 z-20 px-3 py-1.5 rounded-xl bg-gray-900/70 backdrop-blur-md text-white text-[10px] font-mono space-x-3 pointer-events-none border border-white/10 select-none">
                    <span>🖱️ Drag: Orbit Camera</span>
                    <span>Shift+Drag: Pan</span>
                    <span>Wheel: Zoom</span>
                </div>

                <!-- Empty State -->
                <div v-if="!isLoading && dataLake.total_chunks === 0" class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center p-6">
                    <IconFileText class="w-12 h-12 text-gray-300 dark:text-gray-700 mb-3" />
                    <h4 class="text-sm font-bold text-gray-600 dark:text-gray-300 uppercase tracking-wider">No Chunks Embedded Yet</h4>
                    <p class="text-xs text-gray-400 mt-1 max-w-xs">Upload documents into this DataStore to see them projected into the Data Lake.</p>
                </div>

                <!-- Loading State -->
                <div v-if="isLoading" class="absolute inset-0 bg-white/70 dark:bg-gray-950/70 backdrop-blur-sm z-40 flex flex-col items-center justify-center">
                    <IconAnimateSpin class="w-8 h-8 text-blue-600 animate-spin mb-2" />
                    <span class="text-xs font-black uppercase text-gray-700 dark:text-gray-300 tracking-widest">
                        Projecting {{ dimensions }}D {{ reductionMethod.toUpperCase() }} Cloud...
                    </span>
                </div>
            </div>

            <!-- Documents & Centroids Sidebar with Multi-Selection -->
            <aside class="w-64 sm:w-80 shrink-0 border-l border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/40 flex flex-col z-10 overflow-hidden">
                <div class="p-3 border-b dark:border-gray-800 space-y-2">
                    <div class="flex items-center justify-between">
                        <div>
                            <h4 class="text-xs font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">Document Clusters</h4>
                            <p class="text-[10px] text-gray-400 font-mono">
                                {{ selectedDocumentIds.size > 0 ? `${selectedDocumentIds.size} of ${dataLake.documents.length} selected` : `All ${dataLake.documents.length} documents (${dataLake.total_chunks} chunks)` }}
                            </p>
                        </div>
                        <div class="flex items-center gap-1.5">
                            <button 
                                v-if="selectedDocumentIds.size > 0" 
                                @click="zoomToSelectedDocuments(true)" 
                                class="btn btn-secondary btn-xs py-0.5 px-2 text-[10px] font-bold text-purple-600 dark:text-purple-300"
                                title="Fit Camera to Selected Documents"
                            >
                                Fit Selected
                            </button>
                            <button 
                                v-if="selectedDocumentIds.size > 0" 
                                @click="clearDocumentFilter" 
                                class="text-[10px] font-bold text-blue-500 hover:underline cursor-pointer"
                            >
                                Clear
                            </button>
                            <button 
                                v-else-if="dataLake.documents.length > 1" 
                                @click="selectAllDocuments" 
                                class="text-[10px] font-bold text-gray-400 hover:text-blue-500 cursor-pointer"
                            >
                                Select All
                            </button>
                        </div>
                    </div>
                </div>

                <div class="grow overflow-y-auto custom-scrollbar p-2 space-y-1.5">
                    <div 
                        v-for="doc in dataLake.documents" 
                        :key="doc.id"
                        @click="toggleDocumentSelection(doc.id, true)"
                        class="p-2 rounded-xl text-xs transition-all border flex items-center justify-between gap-2 group cursor-pointer"
                        :class="[
                            isDocumentSelected(doc.id)
                                ? 'bg-white dark:bg-gray-800 border-blue-500 shadow-sm font-bold'
                                : (selectedDocumentIds.size > 0
                                    ? 'border-transparent text-gray-400 opacity-60 hover:opacity-100 hover:bg-white/60 dark:hover:bg-gray-850'
                                    : 'border-transparent hover:bg-white dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300')
                        ]"
                    >
                        <!-- Left: Checkbox + Color & Symbol Pill -->
                        <div class="flex items-center gap-2 min-w-0 grow">
                            <input 
                                type="checkbox"
                                :checked="isDocumentSelected(doc.id)"
                                @click.stop="toggleDocumentSelection(doc.id, false)"
                                class="rounded text-blue-600 focus:ring-blue-500 w-3.5 h-3.5 cursor-pointer shrink-0"
                            />
                            <span 
                                class="w-5 h-5 rounded-lg flex items-center justify-center text-xs font-black shrink-0 text-white shadow-xs"
                                :style="{ backgroundColor: doc.color }"
                                :title="`Center of gravity sign: ${doc.symbol}`"
                            >
                                {{ getShapeGlyph(doc.symbol) }}
                            </span>
                            <span class="truncate text-xs font-medium" :title="doc.name">{{ doc.name }}</span>
                        </div>

                        <!-- Right: Actions & Chunk Count -->
                        <div class="flex items-center gap-1.5 shrink-0">
                            <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-gray-200/60 dark:bg-gray-700/60 text-gray-600 dark:text-gray-300">
                                {{ doc.chunk_count }}
                            </span>
                            <button 
                                type="button"
                                @click.stop="soloDocument(doc.id)"
                                class="p-1 rounded-lg text-gray-400 hover:text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-950/40 transition-colors cursor-pointer"
                                title="Solo this document"
                            >
                                <span class="text-[10px]">🎯</span>
                            </button>
                            <button 
                                type="button"
                                @click.stop="viewDocument(doc)" 
                                class="p-1 rounded-lg text-gray-400 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950/40 transition-colors cursor-pointer"
                                title="Inspect Full Document"
                            >
                                <IconFileText class="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>
                </div>
            </aside>

            <!-- Chunk Inspector Drawer (Opens when individual chunk is clicked) -->
            <Transition
                enter-active-class="transition-all duration-300 ease-out"
                enter-from-class="translate-x-full"
                enter-to-class="translate-x-0"
                leave-active-class="transition-all duration-200 ease-in"
                leave-from-class="translate-x-0"
                leave-to-class="translate-x-full"
            >
                <aside v-if="selectedPoint" class="w-80 lg:w-96 shrink-0 h-full border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col z-30 shadow-2xl p-5 space-y-4 overflow-y-auto custom-scrollbar absolute right-0 inset-y-0">
                    <div class="flex items-center justify-between border-b dark:border-gray-800 pb-3">
                        <div class="flex items-center gap-2">
                            <span class="w-3.5 h-3.5 rounded-full" :style="{ backgroundColor: selectedPoint.color }"></span>
                            <h4 class="font-black text-sm uppercase tracking-wider text-gray-800 dark:text-gray-200">Chunk Inspector</h4>
                        </div>
                        <button @click="selectedPoint = null" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg cursor-pointer">✕</button>
                    </div>

                    <div>
                        <span class="text-[10px] font-bold uppercase text-gray-400">Document</span>
                        <div class="font-bold text-sm text-gray-900 dark:text-white mt-0.5">{{ selectedPoint.document_name }}</div>
                    </div>

                    <div class="flex items-center justify-between text-xs p-2.5 bg-gray-50 dark:bg-gray-800/60 rounded-xl border dark:border-gray-700/60 font-mono">
                        <span>Chunk Index: <b>#{{ selectedPoint.chunk_index }}</b></span>
                        <span>Length: <b>{{ selectedPoint.full_text.length }} chars</b></span>
                    </div>

                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <span class="text-[10px] font-bold uppercase text-gray-400">Full Text Content</span>
                            <button @click="copyText(selectedPoint.full_text)" class="text-xs text-blue-500 hover:underline flex items-center gap-1 cursor-pointer">
                                <IconCopy class="w-3.5 h-3.5" /> Copy
                            </button>
                        </div>
                        <div class="p-3 bg-gray-50 dark:bg-gray-950 rounded-xl border dark:border-gray-800 text-xs font-mono max-h-64 overflow-y-auto custom-scrollbar leading-relaxed whitespace-pre-wrap text-gray-800 dark:text-gray-200">
                            {{ selectedPoint.full_text }}
                        </div>
                    </div>

                    <div v-if="selectedPoint.metadata && Object.keys(selectedPoint.metadata).length > 0">
                        <span class="text-[10px] font-bold uppercase text-gray-400 block mb-1">Metadata</span>
                        <JsonRenderer :json="selectedPoint.metadata" class="p-2.5 bg-gray-50 dark:bg-gray-950 rounded-xl border dark:border-gray-800 text-[10px]" />
                    </div>
                </aside>
            </Transition>
        </div>

        <!-- ── Interactive Document Viewer Modal (Triggered on Centroid Sign Click) ── -->
        <Teleport to="body">
            <div 
                v-if="isDocViewerOpen" 
                @click.self="isDocViewerOpen = false" 
                class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150"
            >
                <div class="bg-white dark:bg-gray-900 w-full max-w-4xl rounded-3xl shadow-2xl border border-gray-200 dark:border-gray-800 overflow-hidden flex flex-col max-h-[88vh] animate-in zoom-in-95 duration-150">
                    
                    <!-- Header -->
                    <div class="px-6 py-4 border-b dark:border-gray-800 bg-gray-50/80 dark:bg-gray-900 flex items-center justify-between gap-4">
                        <div class="flex items-center gap-3 min-w-0">
                            <span 
                                class="w-8 h-8 rounded-xl flex items-center justify-center text-sm font-black shrink-0 text-white shadow-sm"
                                :style="{ backgroundColor: viewingDoc.color }"
                            >
                                {{ getShapeGlyph(viewingDoc.symbol) }}
                            </span>
                            <div class="min-w-0">
                                <h3 class="font-black text-base text-gray-900 dark:text-white truncate">
                                    {{ viewingDoc.name }}
                                </h3>
                                <p class="text-[11px] text-gray-400 font-mono mt-0.5">
                                    Document Center of Gravity • {{ viewingDoc.chunkCount }} Chunk(s) Indexed
                                </p>
                            </div>
                        </div>

                        <div class="flex items-center gap-2 shrink-0">
                            <button @click="copyText(viewingDoc.content)" class="btn btn-secondary btn-xs flex items-center gap-1.5" title="Copy Text">
                                <IconCopy class="w-3.5 h-3.5" />
                                <span>Copy Text</span>
                            </button>
                            <button @click="downloadCurrentDocument" class="btn btn-secondary btn-xs flex items-center gap-1.5" title="Download Document">
                                <IconArrowDownTray class="w-3.5 h-3.5" />
                                <span>Download</span>
                            </button>
                            <button @click="isDocViewerOpen = false" class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg cursor-pointer">
                                <IconXMark class="w-5 h-5" />
                            </button>
                        </div>
                    </div>

                    <!-- Body Content -->
                    <div class="p-6 overflow-y-auto custom-scrollbar grow bg-white dark:bg-gray-950">
                        <div v-if="viewingDoc.isLoading" class="py-20 flex flex-col items-center justify-center gap-3 text-gray-400">
                            <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
                            <span class="text-xs font-bold uppercase tracking-wider">Reconstructing document text from SafeStore...</span>
                        </div>
                        <div v-else-if="viewingDoc.error" class="p-4 bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 rounded-xl text-xs border border-red-200 dark:border-red-800">
                            {{ viewingDoc.error }}
                        </div>
                        <div v-else class="space-y-4">
                            <!-- Stats Strip -->
                            <div class="flex items-center gap-4 text-xs font-mono text-gray-400 p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-800">
                                <span>Total Length: <b>{{ viewingDoc.content.length.toLocaleString() }}</b> chars</span>
                                <span>Words: <b>{{ viewingDoc.content.split(/\s+/).filter(Boolean).length.toLocaleString() }}</b></span>
                                <span>Indexed Chunks: <b>{{ viewingDoc.chunkCount }}</b></span>
                            </div>

                            <!-- Document Text -->
                            <div class="p-4 bg-gray-50/50 dark:bg-gray-900/60 rounded-2xl border dark:border-gray-800 font-mono text-xs leading-relaxed whitespace-pre-wrap text-gray-800 dark:text-gray-200 max-h-[60vh] overflow-y-auto custom-scrollbar">
                                {{ viewingDoc.content }}
                            </div>
                        </div>
                    </div>

                    <!-- Footer -->
                    <div class="px-6 py-3 border-t dark:border-gray-800 bg-gray-50 dark:bg-gray-900 flex items-center justify-end">
                        <button @click="isDocViewerOpen = false" class="btn btn-primary btn-sm px-6">
                            Close
                        </button>
                    </div>

                </div>
            </div>
        </Teleport>

    </div>
</template>

<style scoped>
@reference "tailwindcss";

.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>