from app.observability import trace
from typing import TypedDict,Any,NotRequired,Required
from langgraph.graph import StateGraph,START,END
from app.aws import embed,answer
from app.vector import search
from app.config import settings
from app.guardrails import check_input,check_output


class State(TypedDict):
    question: Required[str]
    principal: Required[Any]
    passages: NotRequired[list]
    answer: NotRequired[str]
    sources: NotRequired[list]
    status: NotRequired[str]
    history: NotRequired[list]


@trace("guard")
def guard(state: State) -> dict[str, str]:
    return {'question':check_input(state['question'])}


@trace("retrieve")
def retrieve(state: State) -> dict[str, Any]:
    p=state['principal']
    # Include the most recent user question for short follow-ups such as 'summarize that'.
    prior_questions=[m['content'] for m in state.get('history',[]) if m['role']=='user']
    query=(prior_questions[-1]+'\nFollow-up: '+state['question']) if prior_questions else state['question']
    hits=search(p.tenant,embed(query),p.groups,p.subject)
    hits=[h for h in hits if h['score']>=settings().min_relevance]
    sources=[{'index':i+1,'document_id':h['metadata'].get('document_id',''),'title':h['metadata'].get('title',''), 'page':h['metadata'].get('page',1),'excerpt':h['metadata'].get('text','')[:320]} for i,h in enumerate(hits)]
    return {'passages':hits,'sources':sources}



def route(state: State) -> str:
    return 'generate' if state.get('passages') else 'no_evidence'


@trace("no_evidence")
def no_evidence(state: State) -> dict[str, str]:
    return {'answer':'I could not find supporting evidence in documents you are authorized to access.','status':'no_evidence'}



@trace("generate")
def generate(state: State) -> dict[str, str]:
    evidence='\n\n'.join(f'[{i+1}] {h["metadata"].get("title", "Document")}, page {h["metadata"].get("page",1)}: {h["metadata"].get("text", "")}' for i,h in enumerate(state.get('passages',[])))
    return {'answer':answer(state['question'],evidence,state.get('history',[])),'status':'answered'}



@trace("validate")
def validate(state: State) -> dict[str, str]:
    return {'answer':check_output(state.get('answer',''))}



def make_graph():
    g=StateGraph(State)
    for name,fn in [('guard',guard),('retrieve',retrieve),('no_evidence',no_evidence),('generate',generate),('validate',validate)]:g.add_node(name,fn)
    g.add_edge(START,'guard');g.add_edge('guard','retrieve')
    g.add_conditional_edges('retrieve',route,{'generate':'generate','no_evidence':'no_evidence'})
    g.add_edge('generate','validate');g.add_edge('validate',END);g.add_edge('no_evidence',END)
    return g.compile()



graph=make_graph()



@trace("chat")
def chat(p,question,history=None):
    r=graph.invoke({'principal':p,'question':question,'history':history or []})
    return {'answer':r['answer'],'sources':r.get('sources',[]),'status':r.get('status','answered')}