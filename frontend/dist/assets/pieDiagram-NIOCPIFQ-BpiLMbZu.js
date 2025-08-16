import{p as V}from"./chunk-353BL4L5-CwbrCZVA.js";import{aX as x,aS as z,c7 as j,ab as u,ad as U,ac as J,ae as X,af as Z,ax as q,aw as H,ai as F,ag as K,aJ as Q,aN as Y,b5 as tt,aj as et,aC as at,aL as rt}from"./index-Rf4-wOhF.js";import{p as nt}from"./treemap-75Q7IDZK-_vXkchZb.js";import{d as O}from"./arc-BXtIFvcm.js";import{o as it}from"./ordinal-Cboi1Yqb.js";import"./_baseUniq-1ziEw8wk.js";import"./_basePickBy-Cu_Reo-s.js";import"./clone-CKhLS_Vs.js";import"./init-Gi6I4Gst.js";function st(t,a){return a<t?-1:a>t?1:a>=t?0:NaN}function ot(t){return t}function lt(){var t=ot,a=st,m=null,o=x(0),p=x(z),y=x(0);function i(e){var r,l=(e=j(e)).length,g,w,h=0,c=new Array(l),n=new Array(l),v=+o.apply(this,arguments),A=Math.min(z,Math.max(-z,p.apply(this,arguments)-v)),f,T=Math.min(Math.abs(A)/l,y.apply(this,arguments)),$=T*(A<0?-1:1),d;for(r=0;r<l;++r)(d=n[c[r]=r]=+t(e[r],r,e))>0&&(h+=d);for(a!=null?c.sort(function(S,C){return a(n[S],n[C])}):m!=null&&c.sort(function(S,C){return m(e[S],e[C])}),r=0,w=h?(A-l*$)/h:0;r<l;++r,v=f)g=c[r],d=n[g],f=v+(d>0?d*w:0)+$,n[g]={data:e[g],index:r,value:d,startAngle:v,endAngle:f,padAngle:T};return n}return i.value=function(e){return arguments.length?(t=typeof e=="function"?e:x(+e),i):t},i.sortValues=function(e){return arguments.length?(a=e,m=null,i):a},i.sort=function(e){return arguments.length?(m=e,a=null,i):m},i.startAngle=function(e){return arguments.length?(o=typeof e=="function"?e:x(+e),i):o},i.endAngle=function(e){return arguments.length?(p=typeof e=="function"?e:x(+e),i):p},i.padAngle=function(e){return arguments.length?(y=typeof e=="function"?e:x(+e),i):y},i}var ct=rt.pie,G={sections:new Map,showData:!1},E=G.sections,N=G.showData,ut=structuredClone(ct),pt=u(()=>structuredClone(ut),"getConfig"),gt=u(()=>{E=new Map,N=G.showData,at()},"clear"),dt=u(({label:t,value:a})=>{E.has(t)||(E.set(t,a),F.debug(`added new section: ${t}, with value: ${a}`))},"addSection"),ft=u(()=>E,"getSections"),mt=u(t=>{N=t},"setShowData"),ht=u(()=>N,"getShowData"),P={getConfig:pt,clear:gt,setDiagramTitle:H,getDiagramTitle:q,setAccTitle:Z,getAccTitle:X,setAccDescription:J,getAccDescription:U,addSection:dt,getSections:ft,setShowData:mt,getShowData:ht},vt=u((t,a)=>{V(t,a),a.setShowData(t.showData),t.sections.map(a.addSection)},"populateDb"),St={parse:u(async t=>{const a=await nt("pie",t);F.debug(a),vt(a,P)},"parse")},xt=u(t=>`
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
`,"getStyles"),yt=xt,wt=u(t=>{const a=[...t.entries()].map(o=>({label:o[0],value:o[1]})).sort((o,p)=>p.value-o.value);return lt().value(o=>o.value)(a)},"createPieArcs"),At=u((t,a,m,o)=>{F.debug(`rendering pie chart
`+t);const p=o.db,y=K(),i=Q(p.getConfig(),y.pie),e=40,r=18,l=4,g=450,w=g,h=Y(a),c=h.append("g");c.attr("transform","translate("+w/2+","+g/2+")");const{themeVariables:n}=y;let[v]=tt(n.pieOuterStrokeWidth);v??(v=2);const A=i.textPosition,f=Math.min(w,g)/2-e,T=O().innerRadius(0).outerRadius(f),$=O().innerRadius(f*A).outerRadius(f*A);c.append("circle").attr("cx",0).attr("cy",0).attr("r",f+v/2).attr("class","pieOuterCircle");const d=p.getSections(),S=wt(d),C=[n.pie1,n.pie2,n.pie3,n.pie4,n.pie5,n.pie6,n.pie7,n.pie8,n.pie9,n.pie10,n.pie11,n.pie12],D=it(C);c.selectAll("mySlices").data(S).enter().append("path").attr("d",T).attr("fill",s=>D(s.data.label)).attr("class","pieCircle");let W=0;d.forEach(s=>{W+=s}),c.selectAll("mySlices").data(S).enter().append("text").text(s=>(s.data.value/W*100).toFixed(0)+"%").attr("transform",s=>"translate("+$.centroid(s)+")").style("text-anchor","middle").attr("class","slice"),c.append("text").text(p.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText");const M=c.selectAll(".legend").data(D.domain()).enter().append("g").attr("class","legend").attr("transform",(s,b)=>{const k=r+l,I=k*D.domain().length/2,_=12*r,B=b*k-I;return"translate("+_+","+B+")"});M.append("rect").attr("width",r).attr("height",r).style("fill",D).style("stroke",D),M.data(S).append("text").attr("x",r+l).attr("y",r-l).text(s=>{const{label:b,value:k}=s.data;return p.getShowData()?`${b} [${k}]`:b});const R=Math.max(...M.selectAll("text").nodes().map(s=>(s==null?void 0:s.getBoundingClientRect().width)??0)),L=w+e+r+l+R;h.attr("viewBox",`0 0 ${L} ${g}`),et(h,g,L,i.useMaxWidth)},"draw"),Ct={draw:At},Gt={parser:St,db:P,renderer:Ct,styles:yt};export{Gt as diagram};
