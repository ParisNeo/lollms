//#region packages/core/src/internal/abort.ts
function e(e) {
	let t = Error(e);
	return t.name = "AbortError", t;
}
function t(t, n) {
	if (t?.aborted) throw e(n);
}
//#endregion
//#region packages/core/src/source/model-source.ts
var n = "model source load was aborted", r = "ooxml-model-source-module/v2", i = new Set([
	"docx",
	"xlsx",
	"pptx"
]), a = new Set([
	"http:",
	"https:",
	"file:",
	"blob:"
]), o = [
	"protocol",
	"target",
	"moduleUrl",
	"config"
], s = 8192, c = 32, l = 8192, u = 16, d = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;
function f(e) {
	if (!(e instanceof Uint8Array)) throw TypeError("model source archive must return Uint8Array bytes");
	let t = new Uint8Array(e.byteLength);
	return t.set(e), t.buffer;
}
function p(e, t) {
	if (typeof e != "object" || !e || Array.isArray(e)) throw TypeError("model source module descriptor must be an object");
	let n = Reflect.ownKeys(e);
	if (n.length !== o.length || o.some((e) => !n.includes(e))) throw TypeError("model source module descriptor has unknown or missing fields");
	let c = Object.getOwnPropertyDescriptors(e);
	if (o.some((e) => !c[e]?.enumerable || !("value" in c[e]))) throw TypeError("model source module descriptor fields must be data properties");
	let l = c.protocol.value, u = c.target.value, d = c.moduleUrl.value;
	if (l !== "ooxml-model-source-module/v2") throw TypeError("unsupported model source module protocol");
	if (typeof u != "string" || !i.has(u)) throw TypeError("unsupported model source target");
	if (t !== void 0 && u !== t) throw TypeError(`a ${u} model source module cannot load ${t} input`);
	if (typeof d != "string" || d.length === 0 || d.length > s || d.trim() !== d) throw TypeError("model source moduleUrl must be a nonempty absolute URL");
	let f;
	try {
		f = new URL(d);
	} catch {
		throw TypeError("model source moduleUrl must be a nonempty absolute URL");
	}
	if (!a.has(f.protocol)) throw TypeError("model source moduleUrl protocol is unsupported");
	return Object.freeze({
		protocol: r,
		target: u,
		moduleUrl: d,
		config: m(c.config.value)
	});
}
function m(e) {
	if (!b(e)) throw TypeError("model source config must be a plain object");
	let t = Reflect.ownKeys(e);
	if (t.length > c) throw RangeError(`model source config accepts at most ${c} entries`);
	let n = {};
	for (let r of t) {
		if (typeof r != "string" || !d.test(r)) throw TypeError("model source config keys must be short identifiers");
		let t = Object.getOwnPropertyDescriptor(e, r);
		if (!t?.enumerable || !("value" in t)) throw TypeError("model source config entries must be data properties");
		let i = t.value;
		if (typeof i == "string") {
			if (i.length > l) throw RangeError("model source config string is too long");
		} else if (typeof i == "number") {
			if (!Number.isFinite(i)) throw TypeError("model source config numbers must be finite");
		} else if (typeof i != "boolean" && i !== null) throw TypeError("model source config values must be strings, numbers, booleans or null");
		n[r] = i;
	}
	return Object.freeze(n);
}
async function h(e, r, i, a, o = []) {
	let s = p(e);
	t(a, n);
	let c = await import(
		/* @vite-ignore */
		s.moduleUrl
), l = typeof c == "object" && c ? c.openModelSource : void 0;
	if (typeof l != "function") throw TypeError("model source module must export openModelSource()");
	t(a, n);
	let u = await l(r, s.config, a, o);
	if (typeof u != "object" || !u) throw TypeError("openModelSource() must return an object");
	let d = u, f = d.close;
	if (typeof f != "function") throw TypeError("an opened model source must provide close()");
	let m = !1, h = () => {
		m || (m = !0, f.call(u));
	};
	try {
		let e = i(d.archive), r = g(d.viewDefaults);
		return t(a, n), Object.freeze({
			archive: e,
			viewDefaults: r,
			close: h
		});
	} catch (e) {
		try {
			h();
		} catch {}
		throw e;
	}
}
function g(e) {
	if (e === void 0) return Object.freeze({});
	if (!b(e)) throw TypeError("model source viewDefaults must be a plain object");
	let t = Reflect.ownKeys(e);
	if (t.length > u) throw RangeError("model source viewDefaults has too many entries");
	let n = {};
	for (let r of t) {
		let t = typeof r == "string" ? Object.getOwnPropertyDescriptor(e, r) : void 0;
		if (typeof r != "string" || !d.test(r) || !t?.enumerable || !("value" in t) || typeof t.value != "boolean") throw TypeError("model source viewDefaults entries must be boolean data properties");
		n[r] = t.value;
	}
	return Object.freeze(n);
}
function _(e, t, n) {
	if (typeof e != "object" && typeof e != "function" || e === null) throw TypeError(`${t} model source archive must be an object`);
	for (let r of n) if (typeof e[r] != "function") throw TypeError(`${t} model source archive must implement ${r}()`);
}
function v(e, t) {
	return (typeof e == "object" || typeof e == "function") && e !== null && typeof e[t] == "function";
}
function y(e) {
	return /* @__PURE__ */ Error(`${e} is unsupported for this source`);
}
function b(e) {
	if (typeof e != "object" || !e || Array.isArray(e)) return !1;
	let t = Object.getPrototypeOf(e);
	return t === Object.prototype || t === null;
}
//#endregion
//#region packages/core/src/errors/ooxml-error.ts
var x = class e extends Error {
	code = "ooxml-resource-limit";
	details;
	constructor(t, n) {
		super(t), this.name = "OoxmlResourceLimitError";
		let r = n.violation, i = Object.freeze({
			format: r.format,
			operation: r.operation,
			resource: r.resource,
			metric: r.metric,
			...r.part === void 0 ? {} : { part: r.part },
			limit: r.limit,
			observed: r.observed,
			configurable: r.configurable,
			usage: Object.freeze({
				archiveEntryCount: r.usage.archiveEntryCount,
				declaredInflatedBytes: r.usage.declaredInflatedBytes,
				...r.usage.largestInflatedEntryBytes === void 0 ? {} : { largestInflatedEntryBytes: r.usage.largestInflatedEntryBytes },
				distinctInflatedBytes: r.usage.distinctInflatedBytes,
				operationInflatedBytes: r.usage.operationInflatedBytes
			})
		});
		this.details = Object.freeze({
			stage: n.stage,
			violation: i
		}), Object.setPrototypeOf(this, e.prototype);
	}
}, S = "OOXML_RESOURCE_LIMIT:", C = 128, ee = 256, w = 4096;
function T(e) {
	return typeof e == "number" && Number.isSafeInteger(e) && e >= 0;
}
function E(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) return !1;
	let t = e;
	return T(t.archiveEntryCount) && T(t.declaredInflatedBytes) && (t.largestInflatedEntryBytes === void 0 || T(t.largestInflatedEntryBytes)) && T(t.distinctInflatedBytes) && T(t.operationInflatedBytes);
}
function D(e) {
	return e === "docx" || e === "xlsx" || e === "pptx";
}
function O(e) {
	return e === "container" || e === "decompression" || e === "parsing" || e === "serialization" || e === "layout" || e === "rendering" || e === "worker";
}
function k(e, t) {
	return typeof e == "string" && e.length > 0 && e.length <= t && !/[\u0000-\u001f\u007f]/u.test(e);
}
function A(e) {
	return k(e, C) && /^[a-z0-9][a-z0-9-]*$/u.test(e);
}
function j(e) {
	return !k(e, w) || e.startsWith("/") || e.startsWith("\\") || e.includes("\\") || e.includes("?") || e.includes("#") || e.includes("://") || /^[a-z]:/iu.test(e) ? !1 : e.split("/").every((e) => e !== "" && e !== "." && e !== "..");
}
var M = new Map([
	["archive-entry:declared-inflated-bytes", {
		stage: "container",
		part: "required"
	}],
	["archive-entry:actual-inflated-bytes", {
		stage: "decompression",
		part: "required"
	}],
	["archive:entry-count", {
		stage: "container",
		part: "forbidden"
	}],
	["archive:central-directory-bytes", {
		stage: "container",
		part: "forbidden",
		configurable: !1
	}],
	["archive:distinct-inflated-bytes", {
		stage: "decompression",
		part: "required"
	}],
	["xml-event:bytes", {
		stage: "parsing",
		part: "optional",
		configurable: !1
	}],
	["xml-context:bytes", {
		stage: "parsing",
		part: "optional",
		configurable: !1
	}],
	["image-effect:work", {
		stage: "parsing",
		part: "forbidden",
		configurable: !1
	}],
	["chartex-allocation:elements", {
		stage: "parsing",
		part: "forbidden",
		configurable: !1
	}],
	["chartex-allocation:bytes", {
		stage: "parsing",
		part: "forbidden",
		configurable: !1
	}],
	["chart-cache:points", {
		stage: "parsing",
		part: "forbidden",
		configurable: !1
	}],
	["numbering-marker:bytes", {
		stage: "parsing",
		part: "forbidden",
		configurable: !1
	}],
	["chart-style-formats:entries", {
		stage: "parsing",
		part: "required",
		configurable: !1
	}],
	["chart-custom-number-formats:entries", {
		stage: "parsing",
		part: "required",
		configurable: !1
	}],
	["chart-number-format-bytes:bytes", {
		stage: "parsing",
		part: "required",
		configurable: !1
	}],
	["xml-tree:depth", {
		stage: "parsing",
		part: "optional",
		configurable: !1
	}],
	["worksheet-row:projected-bytes", {
		stage: "parsing",
		part: "optional",
		configurable: !1
	}],
	["worksheet-shell:projected-bytes", {
		stage: "parsing",
		part: "optional",
		configurable: !1
	}],
	["theme-style-reparse:bytes", {
		stage: "parsing",
		part: "forbidden",
		configurable: !1
	}],
	["style-inheritance:depth", {
		stage: "parsing",
		part: "required",
		configurable: !1
	}],
	["complex-field:depth", {
		stage: "parsing",
		part: "forbidden",
		configurable: !1
	}]
]), N = new Set([...M.keys()].map((e) => e.slice(0, e.indexOf(":")))), P = new Set([...M.keys()].map((e) => e.slice(e.indexOf(":") + 1)));
function F(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) return !1;
	let t = e;
	return !D(t.format) || !k(t.operation, ee) || !A(t.resource) || !A(t.metric) || !T(t.limit) || !T(t.observed) || typeof t.configurable != "boolean" || !E(t.usage) ? !1 : !("part" in t) || j(t.part);
}
function I(e) {
	if (!e || typeof e != "object" || Array.isArray(e)) return !1;
	let t = e;
	if (!O(t.stage) || !F(t.violation)) return !1;
	let n = t.violation, r = M.get(`${n.resource}:${n.metric}`);
	return r ? t.stage !== r.stage || r.configurable === !1 && n.configurable !== !1 ? !1 : r.part === "required" ? n.part !== void 0 : r.part === "forbidden" ? n.part === void 0 : !0 : !(N.has(n.resource) && P.has(n.metric));
}
function L(e) {
	let t = e.violation;
	return `OOXML resource limit exceeded${t.part ? ` for ${t.part}` : ""} (${t.resource}, ${e.stage}): ${t.metric} ${t.observed} > ${t.limit}`;
}
function R(e) {
	let t = e instanceof Error ? e.message : String(e);
	if (!t.startsWith(S)) return;
	let n;
	try {
		n = JSON.parse(t.slice(21));
	} catch {
		return;
	}
	if (!n || typeof n != "object") return;
	let r = n;
	if (!(r.code !== "ooxml-resource-limit" || !I(r.details))) return new x(L(r.details), r.details);
}
function z(e) {
	try {
		return e();
	} catch (e) {
		throw e instanceof x || typeof e != "string" && !(e instanceof Error) ? e : R(e) ?? e;
	}
}
//#endregion
//#region packages/core/src/worker/wasm-guard.ts
function te(e) {
	let t = globalThis.WebAssembly?.RuntimeError;
	return t && e instanceof t || e instanceof RangeError ? !0 : e instanceof Error ? e.name === "RuntimeError" || e.name === "CompileError" || e.name === "LinkError" || e.name === "InternalError" || e.name === "OOMError" : !1;
}
//#endregion
//#region packages/core/src/source/worker-model-source.ts
function B(e, t) {
	return new Proxy(e, { get(e, n) {
		if (n === t) return (...n) => new Uint8Array(f(Reflect.apply(e[t], e, n)));
		let r = Reflect.get(e, n);
		return typeof r == "function" ? r.bind(e) : r;
	} });
}
function V(e, t) {
	try {
		return z(e);
	} catch (e) {
		if (te(e)) try {
			t();
		} catch {}
		throw e;
	}
}
//#endregion
//#region packages/xlsx/src/internal/host-layout.ts
var H = "xlsx-host-layout-request", U = 4096, W = 255, G = 65535 / 20, K = 4096;
function q(e) {
	if (!(e instanceof Uint8Array) || e.byteLength > U) throw RangeError("XLSX host layout request byte budget exceeded");
	let t;
	try {
		t = JSON.parse(new TextDecoder("utf-8", { fatal: !0 }).decode(e));
	} catch {
		throw TypeError("invalid XLSX host layout request");
	}
	return t === null ? null : J(t);
}
function J(e) {
	if (typeof e != "object" || !e || Array.isArray(e)) throw TypeError("invalid XLSX host layout font");
	let t = Object.keys(e), n = [
		"family",
		"sizePt",
		"bold",
		"italic"
	];
	if (t.length !== n.length || !n.every((t) => Object.hasOwn(e, t))) throw TypeError("invalid XLSX host layout font");
	let { family: r, sizePt: i, bold: a, italic: o } = e;
	if (typeof r != "string" || r.length === 0 || r.length > W || typeof i != "number" || !Number.isFinite(i) || i <= 0 || i > G || typeof a != "boolean" || typeof o != "boolean") throw TypeError("invalid XLSX host layout font");
	return Object.freeze({
		family: r,
		sizePt: i,
		bold: a,
		italic: o
	});
}
function Y(e) {
	return typeof e == "number" && Number.isInteger(e) && e >= 1 && e <= K ? e : void 0;
}
async function X(e, t) {
	if (typeof e.host_layout_request != "function") return;
	if (typeof e.configure_host_layout != "function") throw TypeError("XLSX model source archive must implement configure_host_layout()");
	let n = q(e.host_layout_request()), r = n ? Y(await t(n)) : void 0;
	return e.configure_host_layout(r), r;
}
var Z = 1;
function Q(e, t) {
	let n = Z++;
	return new Promise((r) => {
		let i = (t) => {
			let a = t.data;
			!$(a) || a.requestId !== n || (e.removeEventListener("message", i), r(Y(a.maximumDigitWidth)));
		};
		e.addEventListener("message", i);
		try {
			e.postMessage({
				type: H,
				requestId: n,
				font: t
			});
		} catch {
			e.removeEventListener("message", i), r(void 0);
		}
	});
}
function $(e) {
	return typeof e == "object" && !!e && e.type === "xlsx-host-layout-result" && typeof e.requestId == "number";
}
//#endregion
//#region packages/xlsx/src/internal/worker-worksheet-source.ts
var ne = [
	"open_sheet_cursor",
	"pull_sheet_cursor",
	"sheet_cursor_pull_finished",
	"acknowledge_sheet_cursor_terminal",
	"cancel_sheet_cursor",
	"close_sheet_cursor",
	"assert_healthy",
	"parse",
	"extract_image"
];
function re(e) {
	return _(e, "XLSX", ne), e;
}
function ie(e) {
	let [t] = Object.keys(e);
	if (t !== void 0) throw TypeError(`unsupported XLSX model source view default: ${t}`);
}
var ae = (e, t, n) => h(e, t, re, void 0, n), oe = class {
	ooxmlHost;
	openSource;
	modelSource;
	measuredMaximumDigitWidth;
	copyBytes(e) {
		return f(e);
	}
	isHostLayoutResult(e) {
		return $(e);
	}
	requestHostLayoutFromPage(e, t) {
		return Q(e, t);
	}
	extractImage(e) {
		return this.execute((t) => this.copyBytes(t.extract_image(e)));
	}
	constructor(e, t = ae) {
		this.ooxmlHost = e, this.openSource = t;
	}
	get kind() {
		return this.modelSource ? "model-source" : "ooxml";
	}
	async openModelSource(e, t, n, r = []) {
		if (this.modelSource || this.ooxmlHost.archive) throw Error("Workbook source already loaded");
		let i = await this.openSource(t, e, r);
		try {
			if (ie(i.viewDefaults), this.modelSource || this.ooxmlHost.archive) throw Error("Workbook source open was superseded");
		} catch (e) {
			try {
				i.close();
			} catch {}
			throw e;
		}
		let a = B(i.archive, "pull_sheet_cursor"), o = {
			archive: i.archive,
			transferArchive: a,
			close: i.close
		};
		this.modelSource = o;
		try {
			if (this.measuredMaximumDigitWidth = await X(i.archive, n), this.modelSource !== o) throw Error("Workbook source open was superseded");
		} catch (e) {
			if (this.modelSource === o) try {
				this.closeModelSource();
			} catch {}
			throw e;
		}
	}
	get maximumDigitWidth() {
		return this.measuredMaximumDigitWidth;
	}
	cursor() {
		return this.modelSource?.archive ?? this.ooxmlHost.archive;
	}
	execute(e) {
		let t = this.modelSource;
		if (!t) {
			let t = this.ooxmlHost.archive;
			if (!t) throw Error("Workbook not loaded");
			return this.ooxmlHost.run(() => e(t));
		}
		return V(() => e(t.transferArchive), () => {
			this.modelSource === t && this.closeModelSource();
		});
	}
	resourceUsage() {
		let e = this.modelSource;
		if (e) return v(e.archive, "resource_usage") ? this.execute(() => e.archive.resource_usage()) : void 0;
		let t = this.ooxml();
		return this.ooxmlHost.run(() => t.resource_usage());
	}
	toMarkdown() {
		let e = this.modelSource;
		if (e) {
			if (!v(e.archive, "to_markdown")) throw y("Markdown conversion");
			return this.execute(() => e.archive.to_markdown());
		}
		let t = this.ooxml();
		return this.ooxmlHost.run(() => t.to_markdown());
	}
	closeModelSource() {
		let e = this.modelSource;
		this.modelSource = void 0, this.measuredMaximumDigitWidth = void 0, e?.close();
	}
	ooxml() {
		let e = this.ooxmlHost.archive;
		if (!e) throw Error("Workbook not loaded");
		return e;
	}
};
//#endregion
export { oe as WorkerWorksheetSourceOwner };
