import{u as N,al as B,c as m,N as c,l as g,o as r,a as y,w as h,b as a,d as T,aD as q,g as _,h as V,f as k,Y as I,W as w,ak as U,e as u,F as C,r as D,t as p,ap as j,aq as F}from"./index-CcQIYPJ6.js";import{_ as H}from"./GenericModal-B5oVoOXX.js";const O={class:"space-y-4 p-1 h-full flex flex-col"},$={class:"grid grid-cols-1 md:grid-cols-3 gap-4"},E={class:"md:col-span-2"},J={class:"relative mt-1"},R={class:"absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"},W=["value"],Y={key:0,class:"flex flex-wrap gap-2 py-1"},G=["onClick"],Q={class:"flex-grow flex flex-col min-h-[400px]"},K={class:"flex-grow border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden relative shadow-inner"},P={class:"flex justify-end gap-3"},X=["disabled"],ae={__name:"CreateArtefactModal",setup(z){const o=N(),b=B(),S=m(()=>o.modalData("createArtefact")),f=m(()=>{var l;return((l=S.value)==null?void 0:l.discussionId)||b.currentDiscussionId}),n=c(""),s=c(""),d=c(!1),i=c("markdown"),v=[{id:"markdown",name:"Markdown",ext:".md"},{id:"python",name:"Python",ext:".py"},{id:"html",name:"HTML",ext:".html"},{id:"javascript",name:"Javascript",ext:".js"},{id:"typescript",name:"Typescript",ext:".ts"},{id:"css",name:"CSS",ext:".css"},{id:"svg",name:"SVG",ext:".svg"},{id:"mermaid",name:"Mermaid Diagram",ext:".mermaid"},{id:"latex",name:"LaTeX",ext:".tex"},{id:"json",name:"JSON",ext:".json"},{id:"yaml",name:"YAML",ext:".yaml"},{id:"sql",name:"SQL",ext:".sql"},{id:"cpp",name:"C++",ext:".cpp"},{id:"code",name:"Generic Code",ext:".txt"}],M={mermaid:[{label:"Flowchart",code:`graph TD
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
\\end{equation}`}],svg:[{label:"Circle",code:'<circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />'},{label:"Rect",code:'<rect width="300" height="100" style="fill:rgb(0,0,255);stroke-width:3;stroke:rgb(0,0,0)" />'}]},x=m(()=>M[i.value]||[]);g(()=>o.isModalOpen("createArtefact"),l=>{l&&(n.value="Untitled Document.md",s.value="",i.value="markdown")}),g(i,l=>{const e=v.find(t=>t.id===l);if(e&&n.value.includes(".")){const t=n.value.split(".")[0];n.value=t+e.ext}});function A(l){s.value.trim()?s.value+=`

`+l:s.value=l}async function L(){if(!f.value){o.addNotification("No discussion selected.","error");return}if(!n.value.trim()){o.addNotification("Title is required.","warning");return}d.value=!0;try{await b.createManualArtefact({discussionId:f.value,title:n.value.trim(),content:s.value,imagesB64:[]}),o.closeModal("createArtefact")}finally{d.value=!1}}return(l,e)=>(r(),y(H,{modalName:"createArtefact",title:"Create New Document",maxWidthClass:"max-w-4xl"},{body:h(()=>[a("div",O,[a("div",$,[a("div",E,[e[4]||(e[4]=a("label",{for:"artefact-title",class:"label"},"Document Title",-1)),a("div",J,[a("div",R,[k(I,{class:"h-4 w-4 text-gray-400"})]),w(a("input",{id:"artefact-title","onUpdate:modelValue":e[0]||(e[0]=t=>n.value=t),type:"text",class:"input-field pl-10",placeholder:"e.g. My Notes.md",required:""},null,512),[[U,n.value]])])]),a("div",null,[e[5]||(e[5]=a("label",{for:"artefact-type",class:"label"},"Language / Format",-1)),w(a("select",{"onUpdate:modelValue":e[1]||(e[1]=t=>i.value=t),class:"input-field mt-1"},[(r(),u(C,null,D(v,t=>a("option",{key:t.id,value:t.id},p(t.name)+" ("+p(t.ext)+") ",9,W)),64))],512),[[j,i.value]])])]),x.value.length>0?(r(),u("div",Y,[e[6]||(e[6]=a("span",{class:"text-[10px] font-black uppercase text-gray-400 self-center mr-2"},"Quick Snippets:",-1)),(r(!0),u(C,null,D(x.value,t=>(r(),u("button",{key:t.label,onClick:Z=>A(t.code),class:"px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-blue-500 hover:text-white text-[10px] font-bold transition-all border dark:border-gray-700"}," + "+p(t.label),9,G))),128))])):_("",!0),a("div",Q,[e[7]||(e[7]=a("label",{class:"label mb-1"},"Content",-1)),a("div",K,[k(F,{modelValue:s.value,"onUpdate:modelValue":e[2]||(e[2]=t=>s.value=t),class:"h-full absolute inset-0",language:i.value,allowedModes:"both",placeholder:"Start typing or use a snippet above..."},null,8,["modelValue","language"])])])])]),footer:h(()=>[a("div",P,[a("button",{onClick:e[3]||(e[3]=t=>T(o).closeModal("createArtefact")),type:"button",class:"btn btn-secondary"},"Cancel"),a("button",{onClick:L,type:"button",class:"btn btn-primary",disabled:d.value||!n.value.trim()},[d.value?(r(),y(q,{key:0,class:"w-4 h-4 mr-2 animate-spin"})):_("",!0),e[8]||(e[8]=V(" Create & Load "))],8,X)])]),_:1}))}};export{ae as default};
