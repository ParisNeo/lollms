import{w as h,h as r,E as _,G as k,t as a,V as B,l as w,C as N,u as c,x as C,y as S,z as V,k as u,F as D,B as M,M as q,b as m,c as p}from"./vendor-CapARd98.js";import{u as I,q as j,o as F,j as U,ac as O,h as E}from"./index-ClIbc1qP.js";import"./vendor-highlight-DIj44xKl.js";import"./vendor-viz-Cpp3fzDc.js";const H={class:"space-y-4 p-1 h-full flex flex-col"},R={class:"grid grid-cols-1 md:grid-cols-3 gap-4"},G={class:"md:col-span-2"},J={class:"relative mt-1"},$={class:"absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"},Q=["value"],W={key:0,class:"flex flex-wrap gap-2 py-1"},Y=["onClick"],z={class:"grow flex flex-col min-h-[400px]"},K={class:"grow border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden relative shadow-inner"},P={class:"flex justify-end gap-3"},X=["disabled"],se={__name:"CreateArtefactModal",setup(Z){const i=I(),v=j(),x=p(()=>i.modalData("createArtefact")),b=p(()=>x.value?.discussionId||v.currentDiscussionId),f=p(()=>!!x.value?.isLibraryOnly||!b.value),l=m(""),s=m(""),d=m(!1),o=m("markdown"),g=[{id:"markdown",name:"Markdown",ext:".md"},{id:"python",name:"Python",ext:".py"},{id:"html",name:"HTML",ext:".html"},{id:"javascript",name:"Javascript",ext:".js"},{id:"typescript",name:"Typescript",ext:".ts"},{id:"css",name:"CSS",ext:".css"},{id:"svg",name:"SVG",ext:".svg"},{id:"mermaid",name:"Mermaid Diagram",ext:".mermaid"},{id:"latex",name:"LaTeX",ext:".tex"},{id:"json",name:"JSON",ext:".json"},{id:"yaml",name:"YAML",ext:".yaml"},{id:"sql",name:"SQL",ext:".sql"},{id:"cpp",name:"C++",ext:".cpp"},{id:"code",name:"Generic Code",ext:".txt"}],L={mermaid:[{label:"Flowchart",code:`graph TD
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
\\end{equation}`}],svg:[{label:"Circle",code:'<circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />'},{label:"Rect",code:'<rect width="300" height="100" style="fill:rgb(0,0,255);stroke-width:3;stroke:rgb(0,0,0)" />'}]},y=p(()=>L[o.value]||[]);h(()=>i.isModalOpen("createArtefact"),n=>{n&&(l.value="Untitled Document.md",s.value="",o.value="markdown")}),h(o,n=>{const e=g.find(t=>t.id===n);if(e&&l.value.includes(".")){const t=l.value.split(".")[0];l.value=t+e.ext}});function A(n){s.value.trim()?s.value+=`

`+n:s.value=n}async function T(){if(!f.value&&!b.value){i.addNotification("No discussion selected.","error");return}if(!l.value.trim()){i.addNotification("Title is required.","warning");return}d.value=!0;try{f.value?await v.saveRawArtefactToLibrary({title:l.value.trim(),content:s.value,artefactType:o.value==="markdown"?"document":"code"}):await v.createManualArtefact({discussionId:b.value,title:l.value.trim(),content:s.value,imagesB64:[]}),i.closeModal("createArtefact")}catch(n){console.error("Failed to save artefact:",n)}finally{d.value=!1}}return(n,e)=>(r(),_(E,{modalName:"createArtefact",title:"Create New Document",maxWidthClass:"max-w-4xl"},{body:k(()=>[a("div",H,[a("div",R,[a("div",G,[e[4]||(e[4]=a("label",{for:"artefact-title",class:"label"},"Document Title",-1)),a("div",J,[a("div",$,[C(U,{class:"h-4 w-4 text-gray-400"})]),S(a("input",{id:"artefact-title","onUpdate:modelValue":e[0]||(e[0]=t=>l.value=t),type:"text",class:"input-field pl-10",placeholder:"e.g. My Notes.md",required:""},null,512),[[V,l.value]])])]),a("div",null,[e[5]||(e[5]=a("label",{for:"artefact-type",class:"label"},"Language / Format",-1)),S(a("select",{"onUpdate:modelValue":e[1]||(e[1]=t=>o.value=t),class:"input-field mt-1"},[(r(),u(D,null,M(g,t=>a("option",{key:t.id,value:t.id},c(t.name)+" ("+c(t.ext)+") ",9,Q)),64))],512),[[q,o.value]])])]),y.value.length>0?(r(),u("div",W,[e[6]||(e[6]=a("span",{class:"text-[10px] font-black uppercase text-gray-400 self-center mr-2"},"Quick Snippets:",-1)),(r(!0),u(D,null,M(y.value,t=>(r(),u("button",{key:t.label,onClick:ee=>A(t.code),class:"px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-blue-500 hover:text-white text-[10px] font-bold transition-all border dark:border-gray-700"}," + "+c(t.label),9,Y))),128))])):w("",!0),a("div",z,[e[7]||(e[7]=a("label",{class:"label mb-1"},"Content",-1)),a("div",K,[C(O,{modelValue:s.value,"onUpdate:modelValue":e[2]||(e[2]=t=>s.value=t),class:"h-full absolute inset-0",language:o.value,allowedModes:"both",placeholder:"Start typing or use a snippet above..."},null,8,["modelValue","language"])])])])]),footer:k(()=>[a("div",P,[a("button",{onClick:e[3]||(e[3]=t=>B(i).closeModal("createArtefact")),type:"button",class:"btn btn-secondary"},"Cancel"),a("button",{onClick:T,type:"button",class:"btn btn-primary px-10",disabled:d.value||!l.value.trim()},[d.value?(r(),_(F,{key:0,class:"w-4 h-4 mr-2 animate-spin"})):w("",!0),N(" "+c(f.value?"Create & Save":"Create & Load"),1)],8,X)])]),_:1}))}};export{se as default};
