import{Ba as e,Ja as t,Oo as n,To as r,Wa as i,Xa as a,Ya as o,Za as s,_o as c,bo as l,eo as u,et as d,fo as f,jo as p,kn as m,qa as h,s as g,to as _,uo as v,xn as y,ya as b,yo as x,za as S}from"./app-stores-iSAqRt0v.js";import{r as C}from"./index-Jj-epoSB.js";var w={class:`space-y-4 p-1 h-full flex flex-col`},T={class:`grid grid-cols-1 md:grid-cols-3 gap-4`},E={class:`md:col-span-2`},D={class:`relative mt-1`},O={class:`absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none`},k=[`value`],A={key:0,class:`flex flex-wrap gap-2 py-1`},j=[`onClick`],M={class:`grow flex flex-col min-h-[400px]`},N={class:`grow border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden relative shadow-inner`},P={class:`flex justify-end gap-3`},F=[`disabled`],I={__name:`CreateArtefactModal`,setup(I){let L=g(),R=b(),z=h(()=>L.modalData(`createArtefact`)),B=h(()=>z.value?.discussionId||R.currentDiscussionId),V=h(()=>!!z.value?.isLibraryOnly||!B.value),H=r(``),U=r(``),W=r(!1),G=r(`markdown`),K=[{id:`markdown`,name:`Markdown`,ext:`.md`},{id:`python`,name:`Python`,ext:`.py`},{id:`html`,name:`HTML`,ext:`.html`},{id:`javascript`,name:`Javascript`,ext:`.js`},{id:`typescript`,name:`Typescript`,ext:`.ts`},{id:`css`,name:`CSS`,ext:`.css`},{id:`svg`,name:`SVG`,ext:`.svg`},{id:`mermaid`,name:`Mermaid Diagram`,ext:`.mermaid`},{id:`latex`,name:`LaTeX`,ext:`.tex`},{id:`json`,name:`JSON`,ext:`.json`},{id:`yaml`,name:`YAML`,ext:`.yaml`},{id:`sql`,name:`SQL`,ext:`.sql`},{id:`cpp`,name:`C++`,ext:`.cpp`},{id:`code`,name:`Generic Code`,ext:`.txt`}],q={mermaid:[{label:`Flowchart`,code:`graph TD
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
\\end{equation}`}],svg:[{label:`Circle`,code:`<circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />`},{label:`Rect`,code:`<rect width="300" height="100" style="fill:rgb(0,0,255);stroke-width:3;stroke:rgb(0,0,0)" />`}]},J=h(()=>q[G.value]||[]);c(()=>L.isModalOpen(`createArtefact`),e=>{e&&(H.value=`Untitled Document.md`,U.value=``,G.value=`markdown`)}),c(G,e=>{let t=K.find(t=>t.id===e);t&&H.value.includes(`.`)&&(H.value=H.value.split(`.`)[0]+t.ext)});function Y(e){U.value.trim()?U.value+=`

`+e:U.value=e}async function X(){if(!V.value&&!B.value){L.addNotification(`No discussion selected.`,`error`);return}if(!H.value.trim()){L.addNotification(`Title is required.`,`warning`);return}W.value=!0;try{V.value?await R.saveRawArtefactToLibrary({title:H.value.trim(),content:U.value,artefactType:G.value===`markdown`?`document`:`code`}):await R.createManualArtefact({discussionId:B.value,title:H.value.trim(),content:U.value,imagesB64:[]}),L.closeModal(`createArtefact`)}catch(e){console.error(`Failed to save artefact:`,e)}finally{W.value=!1}}return(r,c)=>(v(),o(C,{modalName:`createArtefact`,title:`Create New Document`,maxWidthClass:`max-w-4xl`},{body:x(()=>[t(`div`,w,[t(`div`,T,[t(`div`,E,[c[4]||=t(`label`,{for:`artefact-title`,class:`label`},`Document Title`,-1),t(`div`,D,[t(`div`,O,[_(y,{class:`h-4 w-4 text-gray-400`})]),l(t(`input`,{id:`artefact-title`,"onUpdate:modelValue":c[0]||=e=>H.value=e,type:`text`,class:`input-field pl-10`,placeholder:`e.g. My Notes.md`,required:``},null,512),[[e,H.value]])])]),t(`div`,null,[c[5]||=t(`label`,{for:`artefact-type`,class:`label`},`Language / Format`,-1),l(t(`select`,{"onUpdate:modelValue":c[1]||=e=>G.value=e,class:`input-field mt-1`},[(v(),s(i,null,f(K,e=>t(`option`,{key:e.id,value:e.id},p(e.name)+` (`+p(e.ext)+`) `,9,k)),64))],512),[[S,G.value]])])]),J.value.length>0?(v(),s(`div`,A,[c[6]||=t(`span`,{class:`text-[10px] font-black uppercase text-gray-400 self-center mr-2`},`Quick Snippets:`,-1),(v(!0),s(i,null,f(J.value,e=>(v(),s(`button`,{key:e.label,onClick:t=>Y(e.code),class:`px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-blue-500 hover:text-white text-[10px] font-bold transition-all border dark:border-gray-700`},` + `+p(e.label),9,j))),128))])):a(``,!0),t(`div`,M,[c[7]||=t(`label`,{class:`label mb-1`},`Content`,-1),t(`div`,N,[_(d,{modelValue:U.value,"onUpdate:modelValue":c[2]||=e=>U.value=e,class:`h-full absolute inset-0`,language:G.value,allowedModes:`both`,placeholder:`Start typing or use a snippet above...`},null,8,[`modelValue`,`language`])])])])]),footer:x(()=>[t(`div`,P,[t(`button`,{onClick:c[3]||=e=>n(L).closeModal(`createArtefact`),type:`button`,class:`btn btn-secondary`},`Cancel`),t(`button`,{onClick:X,type:`button`,class:`btn btn-primary px-10`,disabled:W.value||!H.value.trim()},[W.value?(v(),o(m,{key:0,class:`w-4 h-4 mr-2 animate-spin`})):a(``,!0),u(` `+p(V.value?`Create & Save`:`Create & Load`),1)],8,F)])]),_:1}))}};export{I as default};