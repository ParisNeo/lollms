import{$ as e,Cn as t,Go as n,Ho as r,Jo as i,No as a,Po as o,Ro as s,Ss as c,Ts as l,Uo as u,Vo as d,Wo as f,Yo as p,c as m,ds as h,ho as g,is as _,ms as v,os as y,pn as b,ps as x,ys as S}from"./app-stores-CqJj2wyP.js";import{r as C}from"./index-C2W-W1yV.js";var w={class:`space-y-4 p-1 h-full flex flex-col`},T={class:`grid grid-cols-1 md:grid-cols-3 gap-4`},E={class:`md:col-span-2`},D={class:`relative mt-1`},O={class:`absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none`},k=[`value`],A={key:0,class:`flex flex-wrap gap-2 py-1`},j=[`onClick`],M={class:`grow flex flex-col min-h-[400px]`},N={class:`grow border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden relative shadow-inner`},P={class:`flex justify-end gap-3`},F=[`disabled`],I={__name:`CreateArtefactModal`,setup(I){let L=m(),R=g(),z=d(()=>L.modalData(`createArtefact`)),B=d(()=>z.value?.discussionId||R.currentDiscussionId),V=d(()=>!!z.value?.isLibraryOnly||!B.value),H=S(``),U=S(``),W=S(!1),G=S(`markdown`),K=[{id:`markdown`,name:`Markdown`,ext:`.md`},{id:`python`,name:`Python`,ext:`.py`},{id:`html`,name:`HTML`,ext:`.html`},{id:`javascript`,name:`Javascript`,ext:`.js`},{id:`typescript`,name:`Typescript`,ext:`.ts`},{id:`css`,name:`CSS`,ext:`.css`},{id:`svg`,name:`SVG`,ext:`.svg`},{id:`mermaid`,name:`Mermaid Diagram`,ext:`.mermaid`},{id:`latex`,name:`LaTeX`,ext:`.tex`},{id:`json`,name:`JSON`,ext:`.json`},{id:`yaml`,name:`YAML`,ext:`.yaml`},{id:`sql`,name:`SQL`,ext:`.sql`},{id:`cpp`,name:`C++`,ext:`.cpp`},{id:`code`,name:`Generic Code`,ext:`.txt`}],q={mermaid:[{label:`Flowchart`,code:`graph TD
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
\\end{equation}`}],svg:[{label:`Circle`,code:`<circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />`},{label:`Rect`,code:`<rect width="300" height="100" style="fill:rgb(0,0,255);stroke-width:3;stroke:rgb(0,0,0)" />`}]},J=d(()=>q[G.value]||[]);h(()=>L.isModalOpen(`createArtefact`),e=>{e&&(H.value=`Untitled Document.md`,U.value=``,G.value=`markdown`)}),h(G,e=>{let t=K.find(t=>t.id===e);if(t&&H.value.includes(`.`)){let e=H.value.split(`.`)[0];H.value=e+t.ext}});function Y(e){U.value.trim()?U.value+=`

`+e:U.value=e}async function X(){if(!V.value&&!B.value){L.addNotification(`No discussion selected.`,`error`);return}if(!H.value.trim()){L.addNotification(`Title is required.`,`warning`);return}W.value=!0;try{V.value?await R.saveRawArtefactToLibrary({title:H.value.trim(),content:U.value,artefactType:G.value===`markdown`?`document`:`code`}):await R.createManualArtefact({discussionId:B.value,title:H.value.trim(),content:U.value,imagesB64:[]}),L.closeModal(`createArtefact`)}catch(e){console.error(`Failed to save artefact:`,e)}finally{W.value=!1}}return(d,m)=>(_(),u(C,{modalName:`createArtefact`,title:`Create New Document`,maxWidthClass:`max-w-4xl`},{body:x(()=>[r(`div`,w,[r(`div`,T,[r(`div`,E,[m[4]||=r(`label`,{for:`artefact-title`,class:`label`},`Document Title`,-1),r(`div`,D,[r(`div`,O,[p(b,{class:`h-4 w-4 text-gray-400`})]),v(r(`input`,{id:`artefact-title`,"onUpdate:modelValue":m[0]||=e=>H.value=e,type:`text`,class:`input-field pl-10`,placeholder:`e.g. My Notes.md`,required:``},null,512),[[o,H.value]])])]),r(`div`,null,[m[5]||=r(`label`,{for:`artefact-type`,class:`label`},`Language / Format`,-1),v(r(`select`,{"onUpdate:modelValue":m[1]||=e=>G.value=e,class:`input-field mt-1`},[(_(),n(s,null,y(K,e=>r(`option`,{key:e.id,value:e.id},l(e.name)+` (`+l(e.ext)+`) `,9,k)),64))],512),[[a,G.value]])])]),J.value.length>0?(_(),n(`div`,A,[m[6]||=r(`span`,{class:`text-[10px] font-black uppercase text-gray-400 self-center mr-2`},`Quick Snippets:`,-1),(_(!0),n(s,null,y(J.value,e=>(_(),n(`button`,{key:e.label,onClick:t=>Y(e.code),class:`px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-blue-500 hover:text-white text-[10px] font-bold transition-all border dark:border-gray-700`},` + `+l(e.label),9,j))),128))])):f(``,!0),r(`div`,M,[m[7]||=r(`label`,{class:`label mb-1`},`Content`,-1),r(`div`,N,[p(e,{modelValue:U.value,"onUpdate:modelValue":m[2]||=e=>U.value=e,class:`h-full absolute inset-0`,language:G.value,allowedModes:`both`,placeholder:`Start typing or use a snippet above...`},null,8,[`modelValue`,`language`])])])])]),footer:x(()=>[r(`div`,P,[r(`button`,{onClick:m[3]||=e=>c(L).closeModal(`createArtefact`),type:`button`,class:`btn btn-secondary`},`Cancel`),r(`button`,{onClick:X,type:`button`,class:`btn btn-primary px-10`,disabled:W.value||!H.value.trim()},[W.value?(_(),u(t,{key:0,class:`w-4 h-4 mr-2 animate-spin`})):f(``,!0),i(` `+l(V.value?`Create & Save`:`Create & Load`),1)],8,F)])]),_:1}))}};export{I as default};