import{bF as S,bA as F,d6 as Z,aV as p,aX as j,aW as X,aY as Y,aZ as q,bf as H,be as J,b0 as z,a_ as K,br as Q,bv as ee,bP as te,b1 as ae,bk as re,bt as ne}from"./index-BztlMlxc.js";import{p as ie}from"./chunk-4BX2VUAB-1Y_6VsAV.js";import{p as se}from"./treemap-75Q7IDZK-C6FPMh_n.js";import{d as I}from"./arc-fSQYVER6.js";import{o as le}from"./ordinal-Cboi1Yqb.js";import"./_baseUniq-fuymJhjX.js";import"./_basePickBy-C8Gh8vf5.js";import"./clone-02rcJcFT.js";import"./init-Gi6I4Gst.js";function oe(e,a){return a<e?-1:a>e?1:a>=e?0:NaN}function ce(e){return e}function ue(){var e=ce,a=oe,f=null,x=S(0),s=S(F),o=S(0);function l(t){var n,c=(t=Z(t)).length,g,y,h=0,u=new Array(c),i=new Array(c),v=+x.apply(this,arguments),A=Math.min(F,Math.max(-F,s.apply(this,arguments)-v)),m,C=Math.min(Math.abs(A)/c,o.apply(this,arguments)),b=C*(A<0?-1:1),d;for(n=0;n<c;++n)(d=i[u[n]=n]=+e(t[n],n,t))>0&&(h+=d);for(a!=null?u.sort(function(w,D){return a(i[w],i[D])}):f!=null&&u.sort(function(w,D){return f(t[w],t[D])}),n=0,y=h?(A-c*b)/h:0;n<c;++n,v=m)g=u[n],d=i[g],m=v+(d>0?d*y:0)+b,i[g]={data:t[g],index:n,value:d,startAngle:v,endAngle:m,padAngle:C};return i}return l.value=function(t){return arguments.length?(e=typeof t=="function"?t:S(+t),l):e},l.sortValues=function(t){return arguments.length?(a=t,f=null,l):a},l.sort=function(t){return arguments.length?(f=t,a=null,l):f},l.startAngle=function(t){return arguments.length?(x=typeof t=="function"?t:S(+t),l):x},l.endAngle=function(t){return arguments.length?(s=typeof t=="function"?t:S(+t),l):s},l.padAngle=function(t){return arguments.length?(o=typeof t=="function"?t:S(+t),l):o},l}var pe=ne.pie,W={sections:new Map,showData:!1},$=W.sections,G=W.showData,ge=structuredClone(pe),de=p(()=>structuredClone(ge),"getConfig"),fe=p(()=>{$=new Map,G=W.showData,re()},"clear"),me=p(({label:e,value:a})=>{if(a<0)throw new Error(`"${e}" has invalid value: ${a}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);$.has(e)||($.set(e,a),z.debug(`added new section: ${e}, with value: ${a}`))},"addSection"),he=p(()=>$,"getSections"),ve=p(e=>{G=e},"setShowData"),Se=p(()=>G,"getShowData"),L={getConfig:de,clear:fe,setDiagramTitle:J,getDiagramTitle:H,setAccTitle:q,getAccTitle:Y,setAccDescription:X,getAccDescription:j,addSection:me,getSections:he,setShowData:ve,getShowData:Se},xe=p((e,a)=>{ie(e,a),a.setShowData(e.showData),e.sections.map(a.addSection)},"populateDb"),ye={parse:p(async e=>{const a=await se("pie",e);z.debug(a),xe(a,L)},"parse")},Ae=p(e=>`
  .pieCircle{
    stroke: ${e.pieStrokeColor};
    stroke-width : ${e.pieStrokeWidth};
    opacity : ${e.pieOpacity};
  }
  .pieOuterCircle{
    stroke: ${e.pieOuterStrokeColor};
    stroke-width: ${e.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${e.pieTitleTextSize};
    fill: ${e.pieTitleTextColor};
    font-family: ${e.fontFamily};
  }
  .slice {
    font-family: ${e.fontFamily};
    fill: ${e.pieSectionTextColor};
    font-size:${e.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${e.pieLegendTextColor};
    font-family: ${e.fontFamily};
    font-size: ${e.pieLegendTextSize};
  }
`,"getStyles"),we=Ae,De=p(e=>{const a=[...e.values()].reduce((s,o)=>s+o,0),f=[...e.entries()].map(([s,o])=>({label:s,value:o})).filter(s=>s.value/a*100>=1).sort((s,o)=>o.value-s.value);return ue().value(s=>s.value)(f)},"createPieArcs"),Ce=p((e,a,f,x)=>{z.debug(`rendering pie chart
`+e);const s=x.db,o=K(),l=Q(s.getConfig(),o.pie),t=40,n=18,c=4,g=450,y=g,h=ee(a),u=h.append("g");u.attr("transform","translate("+y/2+","+g/2+")");const{themeVariables:i}=o;let[v]=te(i.pieOuterStrokeWidth);v??(v=2);const A=l.textPosition,m=Math.min(y,g)/2-t,C=I().innerRadius(0).outerRadius(m),b=I().innerRadius(m*A).outerRadius(m*A);u.append("circle").attr("cx",0).attr("cy",0).attr("r",m+v/2).attr("class","pieOuterCircle");const d=s.getSections(),w=De(d),D=[i.pie1,i.pie2,i.pie3,i.pie4,i.pie5,i.pie6,i.pie7,i.pie8,i.pie9,i.pie10,i.pie11,i.pie12];let T=0;d.forEach(r=>{T+=r});const N=w.filter(r=>(r.data.value/T*100).toFixed(0)!=="0"),k=le(D);u.selectAll("mySlices").data(N).enter().append("path").attr("d",C).attr("fill",r=>k(r.data.label)).attr("class","pieCircle"),u.selectAll("mySlices").data(N).enter().append("text").text(r=>(r.data.value/T*100).toFixed(0)+"%").attr("transform",r=>"translate("+b.centroid(r)+")").style("text-anchor","middle").attr("class","slice"),u.append("text").text(s.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText");const P=[...d.entries()].map(([r,M])=>({label:r,value:M})),E=u.selectAll(".legend").data(P).enter().append("g").attr("class","legend").attr("transform",(r,M)=>{const R=n+c,V=R*P.length/2,B=12*n,U=M*R-V;return"translate("+B+","+U+")"});E.append("rect").attr("width",n).attr("height",n).style("fill",r=>k(r.label)).style("stroke",r=>k(r.label)),E.append("text").attr("x",n+c).attr("y",n-c).text(r=>s.getShowData()?`${r.label} [${r.value}]`:r.label);const _=Math.max(...E.selectAll("text").nodes().map(r=>(r==null?void 0:r.getBoundingClientRect().width)??0)),O=y+t+n+c+_;h.attr("viewBox",`0 0 ${O} ${g}`),ae(h,g,O,l.useMaxWidth)},"draw"),be={draw:Ce},Ne={parser:ye,db:L,renderer:be,styles:we};export{Ne as diagram};
