// frontend/webui/src/services/imageExport.js
//
// Shared image EXPORT pipeline used by the "download" buttons across the app
// (Image Studio tile hover bar, Image Viewer lightbox). Centralises the
// format catalogue, canvas re-encoding, and the dependency-free PDF builder
// so callers only have to fetch a Blob and await `exportImageBlobAsFormat`.

export const EXPORT_FORMATS = [
    { id: 'png',  label: 'PNG',  hint: 'Lossless · alpha',   emoji: '🖼️', extension: 'png',  mime: 'image/png',  lossy: false },
    { id: 'jpeg', label: 'JPG',  hint: 'Smaller · no alpha', emoji: '📷', extension: 'jpg',  mime: 'image/jpeg', lossy: true,  needsFlatten: true },
    { id: 'webp', label: 'WEBP', hint: 'Compact · modern',   emoji: '🌐', extension: 'webp', mime: 'image/webp', lossy: true },
    { id: 'pdf',  label: 'PDF',  hint: 'Document export',    emoji: '📄', extension: 'pdf',  lossy: true,  needsFlatten: true }
];

export function getExportFormat(id) {
    return EXPORT_FORMATS.find(f => f.id === id) || EXPORT_FORMATS[0];
}

export function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1500);
}

// JPEG/PDF have no alpha channel — composite onto solid white first so the
// transparent regions don't turn black after encoding.
export function flattenWithWhiteBackground(sourceCanvas) {
    const bg = document.createElement('canvas');
    bg.width = sourceCanvas.width;
    bg.height = sourceCanvas.height;
    const c = bg.getContext('2d');
    c.fillStyle = '#FFFFFF';
    c.fillRect(0, 0, bg.width, bg.height);
    c.drawImage(sourceCanvas, 0, 0);
    return bg;
}

// Builds a minimal, spec-compliant single-page PDF wrapping a JPEG-compressed
// copy of the canvas (DCTDecode filter). No external library required — we
// assemble the object table, xref and trailer with correct byte offsets.
export function canvasToPdfBlob(canvas, quality = 0.92) {
    return new Promise((resolve, reject) => {
        const w = canvas.width;
        const h = canvas.height;
        canvas.toBlob(async (jpegBlob) => {
            if (!jpegBlob) {
                reject(new Error('Failed to encode JPEG for PDF.'));
                return;
            }
            try {
                const jpegBuf = new Uint8Array(await jpegBlob.arrayBuffer());
                const enc = new TextEncoder();

                const parts = [];
                let byteLen = 0;
                const pushBytes = (u8) => { parts.push(u8); byteLen += u8.length; };
                const pushStr = (s) => pushBytes(enc.encode(s));

                const objOffsets = {};

                pushStr('%PDF-1.4\n');
                pushBytes(new Uint8Array([0x25, 0xE2, 0xE3, 0xCF, 0xD3, 0x0A]));

                objOffsets[1] = byteLen;
                pushStr('1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n');

                objOffsets[2] = byteLen;
                pushStr('2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n');

                objOffsets[3] = byteLen;
                pushStr(`3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>\nendobj\n`);

                objOffsets[4] = byteLen;
                pushStr(`4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${w} /Height ${h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpegBuf.length} >>\nstream\n`);
                pushBytes(jpegBuf);
                pushStr('\nendstream\nendobj\n');

                const contentBytes = enc.encode(`q\n${w} 0 0 ${h} 0 0 cm\n/Im0 Do\nQ\n`);
                objOffsets[5] = byteLen;
                pushStr(`5 0 obj\n<< /Length ${contentBytes.length} >>\nstream\n`);
                pushBytes(contentBytes);
                pushStr('\nendstream\nendobj\n');

                const xrefStart = byteLen;
                let xref = 'xref\n0 6\n0000000000 65535 f \n';
                for (let i = 1; i <= 5; i++) {
                    xref += String(objOffsets[i]).padStart(10, '0') + ' 00000 n \n';
                }
                pushStr(xref);
                pushStr(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF\n`);

                resolve(new Blob(parts, { type: 'application/pdf' }));
            } catch (err) {
                reject(err);
            }
        }, 'image/jpeg', quality);
    });
}

function loadImageFromBlob(blob) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        const url = URL.createObjectURL(blob);
        img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
        img.onerror = (e) => { URL.revokeObjectURL(url); reject(e); };
        img.src = url;
    });
}

/**
 * Re-encodes a source image Blob into the requested format and triggers the
 * browser save dialog.
 *
 * @param {Blob} sourceBlob   Arbitrary image payload (already fetched via auth).
 * @param {object} opts
 * @param {string} opts.format     One of the EXPORT_FORMATS ids ('png'|'jpeg'|'webp'|'pdf').
 * @param {number} [opts.quality]  0.0–1.0; ignored for PNG.
 * @param {string} [opts.filename] Base filename without extension (sanitize upstream).
 * @returns {Promise<{filename: string, extension: string}>}
 */
export async function exportImageBlobAsFormat(sourceBlob, { format, quality = 0.92, filename = 'image' }) {
    const fmt = getExportFormat(format);
    const image = await loadImageFromBlob(sourceBlob);

    const canvas = document.createElement('canvas');
    canvas.width = image.naturalWidth || image.width;
    canvas.height = image.naturalHeight || image.height;
    canvas.getContext('2d').drawImage(image, 0, 0);

    const target = fmt.needsFlatten ? flattenWithWhiteBackground(canvas) : canvas;
    const cleanFilename = (filename || 'image').trim().replace(/\.[^.]+$/, '') || 'image';
    const finalFilename = `${cleanFilename}.${fmt.extension}`;

    if (fmt.id === 'pdf') {
        const pdfBlob = await canvasToPdfBlob(target, quality);
        triggerDownload(pdfBlob, finalFilename);
    } else {
        const blob = await new Promise((res) => target.toBlob(res, fmt.mime, fmt.lossy ? quality : undefined));
        if (!blob) throw new Error(`Failed to encode as ${fmt.label}.`);
        triggerDownload(blob, finalFilename);
    }

    return { filename: finalFilename, extension: fmt.extension };
}