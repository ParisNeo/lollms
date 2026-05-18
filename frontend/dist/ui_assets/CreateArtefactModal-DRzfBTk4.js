import{$ as e,Dt as t,H as n,V as r,c as i,d as a,g as o,h as s,j as c,k as l,l as u,ot as d,r as f,s as p,u as m,z as h}from"./runtime-core.esm-bundler-BTsBJdP6.js";import{I as g,W as _,at as v,ot as y,v as b}from"./auth-CRv-7seU.js";import{t as x}from"./IconAnimateSpin-BcDtc0gq.js";import{t as S}from"./IconFileText-B09haW23.js";import{t as C}from"./GenericModal-BrKFuY2k.js";var w={class:`space-y-4 p-1 h-full flex flex-col`},T={class:`grid grid-cols-1 md:grid-cols-3 gap-4`},E={class:`md:col-span-2`},D={class:`relative mt-1`},O={class:`absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none`},k=[`value`],A={key:0,class:`flex flex-wrap gap-2 py-1`},j=[`onClick`],M={class:`grow flex flex-col min-h-[400px]`},N={class:`grow border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden relative shadow-inner`},P={class:`flex justify-end gap-3`},F=[`disabled`],I={__name:`CreateArtefactModal`,setup(I){let L=_(),R=g(),z=p(()=>L.modalData(`createArtefact`)),B=p(()=>z.value?.discussionId||R.currentDiscussionId),V=e(``),H=e(``),U=e(!1),W=e(`markdown`),G=[{id:`markdown`,name:`Markdown`,ext:`.md`},{id:`python`,name:`Python`,ext:`.py`},{id:`html`,name:`HTML`,ext:`.html`},{id:`javascript`,name:`Javascript`,ext:`.js`},{id:`typescript`,name:`Typescript`,ext:`.ts`},{id:`css`,name:`CSS`,ext:`.css`},{id:`svg`,name:`SVG`,ext:`.svg`},{id:`mermaid`,name:`Mermaid Diagram`,ext:`.mermaid`},{id:`latex`,name:`LaTeX`,ext:`.tex`},{id:`json`,name:`JSON`,ext:`.json`},{id:`yaml`,name:`YAML`,ext:`.yaml`},{id:`sql`,name:`SQL`,ext:`.sql`},{id:`cpp`,name:`C++`,ext:`.cpp`},{id:`code`,name:`Generic Code`,ext:`.txt`}],K={mermaid:[{label:`Flowchart`,code:`graph TD
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
\\end{equation}`}],svg:[{label:`Circle`,code:`<circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />`},{label:`Rect`,code:`<rect width="300" height="100" style="fill:rgb(0,0,255);stroke-width:3;stroke:rgb(0,0,0)" />`}]},q=p(()=>K[W.value]||[]);h(()=>L.isModalOpen(`createArtefact`),e=>{e&&(V.value=`Untitled Document.md`,H.value=``,W.value=`markdown`)}),h(W,e=>{let t=G.find(t=>t.id===e);t&&V.value.includes(`.`)&&(V.value=V.value.split(`.`)[0]+t.ext)});function J(e){H.value.trim()?H.value+=`

`+e:H.value=e}async function Y(){if(!B.value){L.addNotification(`No discussion selected.`,`error`);return}if(!V.value.trim()){L.addNotification(`Title is required.`,`warning`);return}U.value=!0;try{await R.createManualArtefact({discussionId:B.value,title:V.value.trim(),content:H.value,imagesB64:[]}),L.closeModal(`createArtefact`)}finally{U.value=!1}}return(e,p)=>(l(),u(C,{modalName:`createArtefact`,title:`Create New Document`,maxWidthClass:`max-w-4xl`},{body:r(()=>[i(`div`,w,[i(`div`,T,[i(`div`,E,[p[4]||=i(`label`,{for:`artefact-title`,class:`label`},`Document Title`,-1),i(`div`,D,[i(`div`,O,[o(S,{class:`h-4 w-4 text-gray-400`})]),n(i(`input`,{id:`artefact-title`,"onUpdate:modelValue":p[0]||=e=>V.value=e,type:`text`,class:`input-field pl-10`,placeholder:`e.g. My Notes.md`,required:``},null,512),[[y,V.value]])])]),i(`div`,null,[p[5]||=i(`label`,{for:`artefact-type`,class:`label`},`Language / Format`,-1),n(i(`select`,{"onUpdate:modelValue":p[1]||=e=>W.value=e,class:`input-field mt-1`},[(l(),a(f,null,c(G,e=>i(`option`,{key:e.id,value:e.id},t(e.name)+` (`+t(e.ext)+`) `,9,k)),64))],512),[[v,W.value]])])]),q.value.length>0?(l(),a(`div`,A,[p[6]||=i(`span`,{class:`text-[10px] font-black uppercase text-gray-400 self-center mr-2`},`Quick Snippets:`,-1),(l(!0),a(f,null,c(q.value,e=>(l(),a(`button`,{key:e.label,onClick:t=>J(e.code),class:`px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-blue-500 hover:text-white text-[10px] font-bold transition-all border dark:border-gray-700`},` + `+t(e.label),9,j))),128))])):m(``,!0),i(`div`,M,[p[7]||=i(`label`,{class:`label mb-1`},`Content`,-1),i(`div`,N,[o(b,{modelValue:H.value,"onUpdate:modelValue":p[2]||=e=>H.value=e,class:`h-full absolute inset-0`,language:W.value,allowedModes:`both`,placeholder:`Start typing or use a snippet above...`},null,8,[`modelValue`,`language`])])])])]),footer:r(()=>[i(`div`,P,[i(`button`,{onClick:p[3]||=e=>d(L).closeModal(`createArtefact`),type:`button`,class:`btn btn-secondary`},`Cancel`),i(`button`,{onClick:Y,type:`button`,class:`btn btn-primary`,disabled:U.value||!V.value.trim()},[U.value?(l(),u(x,{key:0,class:`w-4 h-4 mr-2 animate-spin`})):m(``,!0),p[8]||=s(` Create & Load `,-1)],8,F)])]),_:1}))}};export{I as default};