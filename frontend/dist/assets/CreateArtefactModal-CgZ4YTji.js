import{Ad as e,Au as t,Bd as n,Gd as r,Hu as i,Jd as a,Ld as o,Md as s,Ms as c,Ps as l,Qu as u,Uu as d,Zd as f,_d as p,_s as m,ad as h,bd as g,dr as _,ds as v,gd as y,hd as b,ju as x,ls as S,md as C,od as w,pd as T,ud as E,ur as D,xd as O,zd as k}from"./app-stores-CzS3xjZ_.js";import{n as A,t as j}from"./GenericModal-aDjX4bt0.js";u(),i(),t(),A(),_(),v(),l(),m();var M={class:`space-y-4 p-1 h-full flex flex-col`},N={class:`grid grid-cols-1 md:grid-cols-3 gap-4`},P={class:`md:col-span-2`},F={class:`relative mt-1`},I={class:`absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none`},L=[`value`],R={key:0,class:`flex flex-wrap gap-2 py-1`},z=[`onClick`],B={class:`grow flex flex-col min-h-[400px]`},V={class:`grow border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden relative shadow-inner`},H={class:`flex justify-end gap-3`},U=[`disabled`],W={__name:`CreateArtefactModal`,setup(t){let i=d(),l=x(),u=T(()=>i.modalData(`createArtefact`)),m=T(()=>u.value?.discussionId||l.currentDiscussionId),_=T(()=>!!u.value?.isLibraryOnly||!m.value),v=r(``),A=r(``),W=r(!1),G=r(`markdown`),K=[{id:`markdown`,name:`Markdown`,ext:`.md`},{id:`python`,name:`Python`,ext:`.py`},{id:`html`,name:`HTML`,ext:`.html`},{id:`javascript`,name:`Javascript`,ext:`.js`},{id:`typescript`,name:`Typescript`,ext:`.ts`},{id:`css`,name:`CSS`,ext:`.css`},{id:`svg`,name:`SVG`,ext:`.svg`},{id:`mermaid`,name:`Mermaid Diagram`,ext:`.mermaid`},{id:`latex`,name:`LaTeX`,ext:`.tex`},{id:`json`,name:`JSON`,ext:`.json`},{id:`yaml`,name:`YAML`,ext:`.yaml`},{id:`sql`,name:`SQL`,ext:`.sql`},{id:`cpp`,name:`C++`,ext:`.cpp`},{id:`code`,name:`Generic Code`,ext:`.txt`}],q={mermaid:[{label:`Flowchart`,code:`graph TD
    A[Start] --> B{Is it?}
    B -- Yes --> C[OK]
    B -- No --> D[End]`},{label:`Sequence`,code:`sequenceDiagram
    Alice->>Bob: Hello Bob, how are you?
    Bob-->>Alice: Jolly good!`},{label:`Class`,code:`classDiagram
    Animal <|-- Duck
    class Animal{
        +int age
        +move()
    }`}],html:[{label:`Image`,code:`<img src="URL" alt="Description" />`},{label:`Link`,code:`<a href="URL">Text</a>`},{label:`Div Container`,code:`<div class="container">
    
</div>`},{label:`Basic Table`,code:`<table>
  <tr>
    <th>Header</th>
  </tr>
  <tr>
    <td>Data</td>
  </tr>
</table>`}],python:[{label:`Main Function`,code:`def main():
    print("Hello World")

if __name__ == "__main__":
    main()`},{label:`Class Template`,code:`class MyClass:
    def __init__(self):
        pass`},{label:`List Comp`,code:`[x for x in range(10) if x % 2 == 0]`}],latex:[{label:`Document`,code:`\\documentclass{article}
\\begin{document}

\\end{document}`},{label:`Equation`,code:`\\begin{equation}
    e=mc^2
\\end{equation}`}],svg:[{label:`Circle`,code:`<circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />`},{label:`Rect`,code:`<rect width="300" height="100" style="fill:rgb(0,0,255);stroke-width:3;stroke:rgb(0,0,0)" />`}]},J=T(()=>q[G.value]||[]);o(()=>i.isModalOpen(`createArtefact`),e=>{e&&(v.value=`Untitled Document.md`,A.value=``,G.value=`markdown`)}),o(G,e=>{let t=K.find(t=>t.id===e);t&&v.value.includes(`.`)&&(v.value=v.value.split(`.`)[0]+t.ext)});function Y(e){A.value.trim()?A.value+=`

`+e:A.value=e}async function X(){if(!_.value&&!m.value){i.addNotification(`No discussion selected.`,`error`);return}if(!v.value.trim()){i.addNotification(`Title is required.`,`warning`);return}W.value=!0;try{_.value?await l.saveRawArtefactToLibrary({title:v.value.trim(),content:A.value,artefactType:G.value===`markdown`?`document`:`code`}):await l.createManualArtefact({discussionId:m.value,title:v.value.trim(),content:A.value,imagesB64:[]}),i.closeModal(`createArtefact`)}catch(e){console.error(`Failed to save artefact:`,e)}finally{W.value=!1}}return(t,r)=>(e(),b(j,{modalName:`createArtefact`,title:`Create New Document`,maxWidthClass:`max-w-4xl`},{body:k(()=>[C(`div`,M,[C(`div`,N,[C(`div`,P,[r[4]||=C(`label`,{for:`artefact-title`,class:`label`},`Document Title`,-1),C(`div`,F,[C(`div`,I,[O(S,{class:`h-4 w-4 text-gray-400`})]),n(C(`input`,{id:`artefact-title`,"onUpdate:modelValue":r[0]||=e=>v.value=e,type:`text`,class:`input-field pl-10`,placeholder:`e.g. My Notes.md`,required:``},null,512),[[w,v.value]])])]),C(`div`,null,[r[5]||=C(`label`,{for:`artefact-type`,class:`label`},`Language / Format`,-1),n(C(`select`,{"onUpdate:modelValue":r[1]||=e=>G.value=e,class:`input-field mt-1`},[(e(),p(E,null,s(K,e=>C(`option`,{key:e.id,value:e.id},f(e.name)+` (`+f(e.ext)+`) `,9,L)),64))],512),[[h,G.value]])])]),J.value.length>0?(e(),p(`div`,R,[r[6]||=C(`span`,{class:`text-[10px] font-black uppercase text-gray-400 self-center mr-2`},`Quick Snippets:`,-1),(e(!0),p(E,null,s(J.value,t=>(e(),p(`button`,{key:t.label,onClick:e=>Y(t.code),class:`px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-blue-500 hover:text-white text-[10px] font-bold transition-all border dark:border-gray-700`},` + `+f(t.label),9,z))),128))])):y(``,!0),C(`div`,B,[r[7]||=C(`label`,{class:`label mb-1`},`Content`,-1),C(`div`,V,[O(D,{modelValue:A.value,"onUpdate:modelValue":r[2]||=e=>A.value=e,class:`h-full absolute inset-0`,language:G.value,allowedModes:`both`,placeholder:`Start typing or use a snippet above...`},null,8,[`modelValue`,`language`])])])])]),footer:k(()=>[C(`div`,H,[C(`button`,{onClick:r[3]||=e=>a(i).closeModal(`createArtefact`),type:`button`,class:`btn btn-secondary`},`Cancel`),C(`button`,{onClick:X,type:`button`,class:`btn btn-primary px-10`,disabled:W.value||!v.value.trim()},[W.value?(e(),b(c,{key:0,class:`w-4 h-4 mr-2 animate-spin`})):y(``,!0),g(` `+f(_.value?`Create & Save`:`Create & Load`),1)],8,U)])]),_:1}))}};export{W as default};