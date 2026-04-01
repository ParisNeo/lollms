import{u as A,al as N,c as p,N as d,l as x,o as r,a as y,w as h,b as a,d as T,aD as B,g as _,h as q,t as u,f as k,Y as V,W as w,ak as U,e as m,F as C,r as I,ap as j,aq as F}from"./index-BJikw9h4.js";import{_ as H}from"./GenericModal-t3lJs2_f.js";const J={class:"space-y-4 p-1 h-full flex flex-col"},O={class:"grid grid-cols-1 md:grid-cols-3 gap-4"},Y={class:"md:col-span-2"},$={class:"relative mt-1"},E={class:"absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"},R=["value"],W={key:0,class:"flex flex-wrap gap-2 py-1"},G=["onClick"],P={class:"flex-grow flex flex-col min-h-[400px]"},Q={class:"flex-grow border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden relative shadow-inner"},K={class:"flex justify-end gap-3"},X=["disabled"],ae={__name:"CreateArtefactModal",setup(z){const s=A(),v=N(),D=p(()=>s.modalData("createArtefact")),b=p(()=>{var n;return((n=D.value)==null?void 0:n.discussionId)||v.currentDiscussionId}),l=d(""),o=d(""),c=d(!1),i=d("markdown"),f=[{id:"markdown",name:"Markdown",ext:".md",icon:"IconMarkdown"},{id:"python",name:"Python",ext:".py",icon:"IconPython"},{id:"html",name:"HTML",ext:".html",icon:"IconHtml"},{id:"javascript",name:"Javascript",ext:".js",icon:"IconJavascript"},{id:"typescript",name:"Typescript",ext:".ts",icon:"IconTypescript"},{id:"css",name:"CSS",ext:".css",icon:"IconCode"},{id:"svg",name:"SVG",ext:".svg",icon:"IconSvg"},{id:"mermaid",name:"Mermaid Diagram",ext:".mermaid",icon:"IconMermaid"},{id:"latex",name:"LaTeX",ext:".tex",icon:"IconLatex"},{id:"json",name:"JSON",ext:".json",icon:"IconJson"},{id:"yaml",name:"YAML",ext:".yaml",icon:"IconYaml"},{id:"sql",name:"SQL",ext:".sql",icon:"IconDatabase"},{id:"cpp",name:"C++",ext:".cpp",icon:"IconCode"},{id:"code",name:"Generic Code",ext:".txt",icon:"IconTerminal"}],S={mermaid:[{label:"Flowchart",code:`graph TD
    A[Start] --> B{Is it?}
    B -- Yes --> C[OK]
    B -- No --> D[End]`},{label:"Sequence",code:`sequenceDiagram
    Alice->>Bob: Hello Bob, how are you?
    Bob-->>Alice: Jolly good!`},{label:"Class",code:`classDiagram
    Animal <|-- Duck
    class Animal{
        +int age
        +move()
    }`}],html:[{label:"Image",code:'<img src="URL" alt="Description" />'},{label:"Link",code:'<a href="URL">Text</a>'},{label:"Div Container",code:`<div class="container">
    
</div>`},{label:"Basic Table",code:`<table>
  <tr>
    <th>Header</th>
  </tr>
  <tr>
    <td>Data</td>
  </tr>
</table>`}],python:[{label:"Main Function",code:`def main():
    print("Hello World")

if __name__ == "__main__":
    main()`},{label:"Class Template",code:`class MyClass:
    def __init__(self):
        pass`},{label:"List Comp",code:"[x for x in range(10) if x % 2 == 0]"}],latex:[{label:"Document",code:`\\documentclass{article}
\\begin{document}

\\end{document}`},{label:"Equation",code:`\\begin{equation}
    e=mc^2
\\end{equation}`}],svg:[{label:"Circle",code:'<circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />'},{label:"Rect",code:'<rect width="300" height="100" style="fill:rgb(0,0,255);stroke-width:3;stroke:rgb(0,0,0)" />'}]},g=p(()=>S[i.value]||[]);x(()=>s.isModalOpen("createArtefact"),n=>{n&&(l.value="Untitled Document.md",o.value="",i.value="markdown")}),x(i,n=>{const e=f.find(t=>t.id===n);if(e&&l.value.includes(".")){const t=l.value.split(".")[0];l.value=t+e.ext}});function M(n){o.value.trim()?o.value+=`

`+n:o.value=n}async function L(){if(!b.value){s.addNotification("No discussion selected.","error");return}if(!l.value.trim()){s.addNotification("Title is required.","warning");return}if(!o.value.trim()){s.addNotification("Content is required.","warning");return}c.value=!0;try{await v.createManualArtefact({discussionId:b.value,title:l.value.trim(),content:o.value,imagesB64:[]}),s.closeModal("createArtefact")}finally{c.value=!1}}return(n,e)=>(r(),y(H,{modalName:"createArtefact",title:"Create New Document",maxWidthClass:"max-w-3xl"},{body:h(()=>[a("div",J,[a("div",O,[a("div",Y,[e[4]||(e[4]=a("label",{for:"artefact-title",class:"label"},"Document Title",-1)),a("div",$,[a("div",E,[k(V,{class:"h-4 w-4 text-gray-400"})]),w(a("input",{id:"artefact-title","onUpdate:modelValue":e[0]||(e[0]=t=>l.value=t),type:"text",class:"input-field pl-10",placeholder:"e.g. My Notes.md",required:""},null,512),[[U,l.value]])])]),a("div",null,[e[5]||(e[5]=a("label",{for:"artefact-type",class:"label"},"Language / Format",-1)),w(a("select",{"onUpdate:modelValue":e[1]||(e[1]=t=>i.value=t),class:"input-field mt-1"},[(r(),m(C,null,I(f,t=>a("option",{key:t.id,value:t.id},u(t.name)+" ("+u(t.ext)+") ",9,R)),64))],512),[[j,i.value]])])]),g.value.length>0?(r(),m("div",W,[e[6]||(e[6]=a("span",{class:"text-[10px] font-black uppercase text-gray-400 self-center mr-2"},"Quick Snippets:",-1)),(r(!0),m(C,null,I(g.value,t=>(r(),m("button",{key:t.label,onClick:Z=>M(t.code),class:"px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-blue-500 hover:text-white text-[10px] font-bold transition-all border dark:border-gray-700"}," + "+u(t.label),9,G))),128))])):_("",!0),a("div",P,[e[7]||(e[7]=a("label",{class:"label mb-1"},"Content",-1)),a("div",Q,[k(F,{modelValue:o.value,"onUpdate:modelValue":e[2]||(e[2]=t=>o.value=t),class:"h-full absolute inset-0",language:i.value,allowedModes:"both",placeholder:"Start typing or use a snippet above..."},null,8,["modelValue","language"])])])])]),footer:h(()=>[a("div",K,[a("button",{onClick:e[3]||(e[3]=t=>T(s).closeModal("createArtefact")),type:"button",class:"btn btn-secondary"},"Cancel"),a("button",{onClick:L,type:"button",class:"btn btn-primary",disabled:c.value||!l.value.trim()||!o.value.trim()},[c.value?(r(),y(B,{key:0,class:"w-4 h-4 mr-2 animate-spin"})):_("",!0),q(" "+u((c.value,"Create & Load")),1)],8,X)])]),_:1}))}};export{ae as default};
