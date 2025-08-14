import{p as y}from"./chunk-353BL4L5-CvwulfEX.js";import{a9 as l,aa as B,ab as S,av as z,au as F,ac as P,ad as E,aH as m,aL as W,ah as T,aA as A,aI as D,aJ as _,ag as w}from"./index-SGK5Kf0r.js";import{p as L}from"./treemap-75Q7IDZK-Bfp5Jaav.js";import"./_baseUniq-Dguomd6_.js";import"./_basePickBy-Coni9Hfc.js";import"./clone-B6-E26G6.js";var x={packet:[]},v=structuredClone(x),N=_.packet,I=l(()=>{const t=m({...N,...D().packet});return t.showBits&&(t.paddingY+=10),t},"getConfig"),Y=l(()=>v.packet,"getPacket"),H=l(t=>{t.length>0&&v.packet.push(t)},"pushWord"),M=l(()=>{A(),v=structuredClone(x)},"clear"),u={pushWord:H,getPacket:Y,getConfig:I,clear:M,setAccTitle:E,getAccTitle:P,setDiagramTitle:F,getDiagramTitle:z,getAccDescription:S,setAccDescription:B},O=1e4,G=l(t=>{y(t,u);let e=-1,o=[],n=1;const{bitsPerRow:s}=u.getConfig();for(let{start:a,end:r,bits:c,label:f}of t.blocks){if(a!==void 0&&r!==void 0&&r<a)throw new Error(`Packet block ${a} - ${r} is invalid. End must be greater than start.`);if(a??(a=e+1),a!==e+1)throw new Error(`Packet block ${a} - ${r??a} is not contiguous. It should start from ${e+1}.`);if(c===0)throw new Error(`Packet block ${a} is invalid. Cannot have a zero bit field.`);for(r??(r=a+(c??1)-1),c??(c=r-a+1),e=r,w.debug(`Packet block ${a} - ${e} with label ${f}`);o.length<=s+1&&u.getPacket().length<O;){const[d,p]=J({start:a,end:r,bits:c,label:f},n,s);if(o.push(d),d.end+1===n*s&&(u.pushWord(o),o=[],n++),!p)break;({start:a,end:r,bits:c,label:f}=p)}}u.pushWord(o)},"populate"),J=l((t,e,o)=>{if(t.start===void 0)throw new Error("start should have been set during first phase");if(t.end===void 0)throw new Error("end should have been set during first phase");if(t.start>t.end)throw new Error(`Block start ${t.start} is greater than block end ${t.end}.`);if(t.end+1<=e*o)return[t,void 0];const n=e*o-1,s=e*o;return[{start:t.start,end:n,label:t.label,bits:n-t.start},{start:s,end:t.end,label:t.label,bits:t.end-s}]},"getNextFittingBlock"),K={parse:l(async t=>{const e=await L("packet",t);w.debug(e),G(e)},"parse")},R=l((t,e,o,n)=>{const s=n.db,a=s.getConfig(),{rowHeight:r,paddingY:c,bitWidth:f,bitsPerRow:d}=a,p=s.getPacket(),i=s.getDiagramTitle(),k=r+c,g=k*(p.length+1)-(i?0:r),b=f*d+2,h=W(e);h.attr("viewbox",`0 0 ${b} ${g}`),T(h,g,b,a.useMaxWidth);for(const[C,$]of p.entries())U(h,$,C,a);h.append("text").text(i).attr("x",b/2).attr("y",g-k/2).attr("dominant-baseline","middle").attr("text-anchor","middle").attr("class","packetTitle")},"draw"),U=l((t,e,o,{rowHeight:n,paddingX:s,paddingY:a,bitWidth:r,bitsPerRow:c,showBits:f})=>{const d=t.append("g"),p=o*(n+a)+a;for(const i of e){const k=i.start%c*r+1,g=(i.end-i.start+1)*r-s;if(d.append("rect").attr("x",k).attr("y",p).attr("width",g).attr("height",n).attr("class","packetBlock"),d.append("text").attr("x",k+g/2).attr("y",p+n/2).attr("class","packetLabel").attr("dominant-baseline","middle").attr("text-anchor","middle").text(i.label),!f)continue;const b=i.end===i.start,h=p-2;d.append("text").attr("x",k+(b?g/2:0)).attr("y",h).attr("class","packetByte start").attr("dominant-baseline","auto").attr("text-anchor",b?"middle":"start").text(i.start),b||d.append("text").attr("x",k+g).attr("y",h).attr("class","packetByte end").attr("dominant-baseline","auto").attr("text-anchor","end").text(i.end)}},"drawWord"),X={draw:R},j={byteFontSize:"10px",startByteColor:"black",endByteColor:"black",labelColor:"black",labelFontSize:"12px",titleColor:"black",titleFontSize:"14px",blockStrokeColor:"black",blockStrokeWidth:"1",blockFillColor:"#efefef"},q=l(({packet:t}={})=>{const e=m(j,t);return`
	.packetByte {
		font-size: ${e.byteFontSize};
	}
	.packetByte.start {
		fill: ${e.startByteColor};
	}
	.packetByte.end {
		fill: ${e.endByteColor};
	}
	.packetLabel {
		fill: ${e.labelColor};
		font-size: ${e.labelFontSize};
	}
	.packetTitle {
		fill: ${e.titleColor};
		font-size: ${e.titleFontSize};
	}
	.packetBlock {
		stroke: ${e.blockStrokeColor};
		stroke-width: ${e.blockStrokeWidth};
		fill: ${e.blockFillColor};
	}
	`},"styles"),rt={parser:K,db:u,renderer:X,styles:q};export{rt as diagram};
