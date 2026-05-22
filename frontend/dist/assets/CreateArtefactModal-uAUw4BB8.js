import{Ad as e,Cs as t,Dd as n,Fd as r,Hu as i,Mu as a,Nu as o,Rd as s,Sd as c,Ts as l,Vd as u,Xu as d,Yu as f,ad as p,bd as m,bu as h,cs as g,dd as _,ed as v,es as y,id as b,kd as x,nr as S,ns as C,od as w,rd as T,sd as E,tr as D,ud as O,xu as k}from"./app-stores-D9-tTiDM.js";import{n as A,t as j}from"./GenericModal-CSPO-8IU.js";i(),a(),h(),A(),S(),C(),l(),g();var M={class:`space-y-4 p-1 h-full flex flex-col`},N={class:`grid grid-cols-1 md:grid-cols-3 gap-4`},P={class:`md:col-span-2`},F={class:`relative mt-1`},I={class:`absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none`},L=[`value`],R={key:0,class:`flex flex-wrap gap-2 py-1`},z=[`onClick`],B={class:`grow flex flex-col min-h-[400px]`},V={class:`grow border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden relative shadow-inner`},H={class:`flex justify-end gap-3`},U=[`disabled`],W={__name:`CreateArtefactModal`,setup(i){let a=o(),l=k(),h=T(()=>a.modalData(`createArtefact`)),g=T(()=>h.value?.discussionId||l.currentDiscussionId),S=r(``),C=r(``),A=r(!1),W=r(`markdown`),G=[{id:`markdown`,name:`Markdown`,ext:`.md`},{id:`python`,name:`Python`,ext:`.py`},{id:`html`,name:`HTML`,ext:`.html`},{id:`javascript`,name:`Javascript`,ext:`.js`},{id:`typescript`,name:`Typescript`,ext:`.ts`},{id:`css`,name:`CSS`,ext:`.css`},{id:`svg`,name:`SVG`,ext:`.svg`},{id:`mermaid`,name:`Mermaid Diagram`,ext:`.mermaid`},{id:`latex`,name:`LaTeX`,ext:`.tex`},{id:`json`,name:`JSON`,ext:`.json`},{id:`yaml`,name:`YAML`,ext:`.yaml`},{id:`sql`,name:`SQL`,ext:`.sql`},{id:`cpp`,name:`C++`,ext:`.cpp`},{id:`code`,name:`Generic Code`,ext:`.txt`}],K={mermaid:[{label:`Flowchart`,code:`graph TD
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
\\end{equation}`}],svg:[{label:`Circle`,code:`<circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />`},{label:`Rect`,code:`<rect width="300" height="100" style="fill:rgb(0,0,255);stroke-width:3;stroke:rgb(0,0,0)" />`}]},q=T(()=>K[W.value]||[]);n(()=>a.isModalOpen(`createArtefact`),e=>{e&&(S.value=`Untitled Document.md`,C.value=``,W.value=`markdown`)}),n(W,e=>{let t=G.find(t=>t.id===e);t&&S.value.includes(`.`)&&(S.value=S.value.split(`.`)[0]+t.ext)});function J(e){C.value.trim()?C.value+=`

`+e:C.value=e}async function Y(){if(!g.value){a.addNotification(`No discussion selected.`,`error`);return}if(!S.value.trim()){a.addNotification(`Title is required.`,`warning`);return}A.value=!0;try{await l.createManualArtefact({discussionId:g.value,title:S.value.trim(),content:C.value,imagesB64:[]}),a.closeModal(`createArtefact`)}finally{A.value=!1}}return(n,r)=>(m(),p(j,{modalName:`createArtefact`,title:`Create New Document`,maxWidthClass:`max-w-4xl`},{body:x(()=>[b(`div`,M,[b(`div`,N,[b(`div`,P,[r[4]||=b(`label`,{for:`artefact-title`,class:`label`},`Document Title`,-1),b(`div`,F,[b(`div`,I,[_(y,{class:`h-4 w-4 text-gray-400`})]),e(b(`input`,{id:`artefact-title`,"onUpdate:modelValue":r[0]||=e=>S.value=e,type:`text`,class:`input-field pl-10`,placeholder:`e.g. My Notes.md`,required:``},null,512),[[d,S.value]])])]),b(`div`,null,[r[5]||=b(`label`,{for:`artefact-type`,class:`label`},`Language / Format`,-1),e(b(`select`,{"onUpdate:modelValue":r[1]||=e=>W.value=e,class:`input-field mt-1`},[(m(),E(v,null,c(G,e=>b(`option`,{key:e.id,value:e.id},u(e.name)+` (`+u(e.ext)+`) `,9,L)),64))],512),[[f,W.value]])])]),q.value.length>0?(m(),E(`div`,R,[r[6]||=b(`span`,{class:`text-[10px] font-black uppercase text-gray-400 self-center mr-2`},`Quick Snippets:`,-1),(m(!0),E(v,null,c(q.value,e=>(m(),E(`button`,{key:e.label,onClick:t=>J(e.code),class:`px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-blue-500 hover:text-white text-[10px] font-bold transition-all border dark:border-gray-700`},` + `+u(e.label),9,z))),128))])):w(``,!0),b(`div`,B,[r[7]||=b(`label`,{class:`label mb-1`},`Content`,-1),b(`div`,V,[_(D,{modelValue:C.value,"onUpdate:modelValue":r[2]||=e=>C.value=e,class:`h-full absolute inset-0`,language:W.value,allowedModes:`both`,placeholder:`Start typing or use a snippet above...`},null,8,[`modelValue`,`language`])])])])]),footer:x(()=>[b(`div`,H,[b(`button`,{onClick:r[3]||=e=>s(a).closeModal(`createArtefact`),type:`button`,class:`btn btn-secondary`},`Cancel`),b(`button`,{onClick:Y,type:`button`,class:`btn btn-primary`,disabled:A.value||!S.value.trim()},[A.value?(m(),p(t,{key:0,class:`w-4 h-4 mr-2 animate-spin`})):w(``,!0),r[8]||=O(` Create & Load `,-1)],8,U)])]),_:1}))}};export{W as default};