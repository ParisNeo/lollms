import{p as V}from"./chunk-353BL4L5-DYNcslSN.js";import{aG as y,aB as z,c0 as U,V as u,X as Z,W as j,Y as Q,Z as X,ag as Y,af as q,a1 as G,$ as H,as as J,aw as K,aQ as tt,a2 as et,al as at,au as rt}from"./index-B6Bc3z59.js";import{p as nt}from"./treemap-75Q7IDZK-BhQ8srBD.js";import{d as P}from"./arc-BHilCElF.js";import{o as it}from"./ordinal-Cboi1Yqb.js";import"./_baseUniq-CpIBHXdj.js";import"./_basePickBy-2iM6Xce1.js";import"./clone-D5gsXs9o.js";import"./init-Gi6I4Gst.js";function st(t,a){return a<t?-1:a>t?1:a>=t?0:NaN}function ot(t){return t}function lt(){var t=ot,a=st,m=null,o=y(0),p=y(z),x=y(0);function i(e){var r,l=(e=U(e)).length,g,w,h=0,c=new Array(l),n=new Array(l),v=+o.apply(this,arguments),A=Math.min(z,Math.max(-z,p.apply(this,arguments)-v)),f,$=Math.min(Math.abs(A)/l,x.apply(this,arguments)),T=$*(A<0?-1:1),d;for(r=0;r<l;++r)(d=n[c[r]=r]=+t(e[r],r,e))>0&&(h+=d);for(a!=null?c.sort(function(S,C){return a(n[S],n[C])}):m!=null&&c.sort(function(S,C){return m(e[S],e[C])}),r=0,w=h?(A-l*T)/h:0;r<l;++r,v=f)g=c[r],d=n[g],f=v+(d>0?d*w:0)+T,n[g]={data:e[g],index:r,value:d,startAngle:v,endAngle:f,padAngle:$};return n}return i.value=function(e){return arguments.length?(t=typeof e=="function"?e:y(+e),i):t},i.sortValues=function(e){return arguments.length?(a=e,m=null,i):a},i.sort=function(e){return arguments.length?(m=e,a=null,i):m},i.startAngle=function(e){return arguments.length?(o=typeof e=="function"?e:y(+e),i):o},i.endAngle=function(e){return arguments.length?(p=typeof e=="function"?e:y(+e),i):p},i.padAngle=function(e){return arguments.length?(x=typeof e=="function"?e:y(+e),i):x},i}var ct=rt.pie,W={sections:new Map,showData:!1},M=W.sections,F=W.showData,ut=structuredClone(ct),pt=u(()=>structuredClone(ut),"getConfig"),gt=u(()=>{M=new Map,F=W.showData,at()},"clear"),dt=u(({label:t,value:a})=>{M.has(t)||(M.set(t,a),G.debug(`added new section: ${t}, with value: ${a}`))},"addSection"),ft=u(()=>M,"getSections"),mt=u(t=>{F=t},"setShowData"),ht=u(()=>F,"getShowData"),R={getConfig:pt,clear:gt,setDiagramTitle:q,getDiagramTitle:Y,setAccTitle:X,getAccTitle:Q,setAccDescription:j,getAccDescription:Z,addSection:dt,getSections:ft,setShowData:mt,getShowData:ht},vt=u((t,a)=>{V(t,a),a.setShowData(t.showData),t.sections.map(a.addSection)},"populateDb"),St={parse:u(async t=>{const a=await nt("pie",t);G.debug(a),vt(a,R)},"parse")},yt=u(t=>`
  .pieCircle{
    stroke: ${t.pieStrokeColor};
    stroke-width : ${t.pieStrokeWidth};
    opacity : ${t.pieOpacity};
  }
  .pieOuterCircle{
    stroke: ${t.pieOuterStrokeColor};
    stroke-width: ${t.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${t.pieTitleTextSize};
    fill: ${t.pieTitleTextColor};
    font-family: ${t.fontFamily};
  }
  .slice {
    font-family: ${t.fontFamily};
    fill: ${t.pieSectionTextColor};
    font-size:${t.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${t.pieLegendTextColor};
    font-family: ${t.fontFamily};
    font-size: ${t.pieLegendTextSize};
  }
`,"getStyles"),xt=yt,wt=u(t=>{const a=[...t.entries()].map(o=>({label:o[0],value:o[1]})).sort((o,p)=>p.value-o.value);return lt().value(o=>o.value)(a)},"createPieArcs"),At=u((t,a,m,o)=>{G.debug(`rendering pie chart
`+t);const p=o.db,x=H(),i=J(p.getConfig(),x.pie),e=40,r=18,l=4,g=450,w=g,h=K(a),c=h.append("g");c.attr("transform","translate("+w/2+","+g/2+")");const{themeVariables:n}=x;let[v]=tt(n.pieOuterStrokeWidth);v??(v=2);const A=i.textPosition,f=Math.min(w,g)/2-e,$=P().innerRadius(0).outerRadius(f),T=P().innerRadius(f*A).outerRadius(f*A);c.append("circle").attr("cx",0).attr("cy",0).attr("r",f+v/2).attr("class","pieOuterCircle");const d=p.getSections(),S=wt(d),C=[n.pie1,n.pie2,n.pie3,n.pie4,n.pie5,n.pie6,n.pie7,n.pie8,n.pie9,n.pie10,n.pie11,n.pie12],D=it(C);c.selectAll("mySlices").data(S).enter().append("path").attr("d",$).attr("fill",s=>D(s.data.label)).attr("class","pieCircle");let N=0;d.forEach(s=>{N+=s}),c.selectAll("mySlices").data(S).enter().append("text").text(s=>(s.data.value/N*100).toFixed(0)+"%").attr("transform",s=>"translate("+T.centroid(s)+")").style("text-anchor","middle").attr("class","slice"),c.append("text").text(p.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText");const b=c.selectAll(".legend").data(D.domain()).enter().append("g").attr("class","legend").attr("transform",(s,k)=>{const E=r+l,L=E*D.domain().length/2,_=12*r,B=k*E-L;return"translate("+_+","+B+")"});b.append("rect").attr("width",r).attr("height",r).style("fill",D).style("stroke",D),b.data(S).append("text").attr("x",r+l).attr("y",r-l).text(s=>{const{label:k,value:E}=s.data;return p.getShowData()?`${k} [${E}]`:k});const I=Math.max(...b.selectAll("text").nodes().map(s=>(s==null?void 0:s.getBoundingClientRect().width)??0)),O=w+e+r+l+I;h.attr("viewBox",`0 0 ${O} ${g}`),et(h,g,O,i.useMaxWidth)},"draw"),Ct={draw:At},Wt={parser:St,db:R,renderer:Ct,styles:xt};export{Wt as diagram};
