"""
EU Multi-Echelon Regional Distribution Network Model
with Washing/Reconditioning for Reusable Transport Packaging (RTP)

Inspired by:
  - "Designing a closed-loop supply chain for reusable packaging materials:
     A risk-averse two-stage stochastic programming model using CVaR"
     (Computers & Industrial Engineering)

18-node network: EU Entry Ports -> Regional DCs -> Retail Regions ->
Collection Points -> Washing Centers -> EU Pooler -> (loop or return)
"""
import numpy as np, random, json, math
import matplotlib; matplotlib.use('Agg')
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict

PORT_ROTTERDAM=1; PORT_HAMBURG=2
DC_NORTH=3; DC_CENTRAL=4; DC_SOUTH=5
WASH_NORTH=6; WASH_SOUTH=7
RETAIL_BENELUX=8; RETAIL_GERMANY=9; RETAIL_FRANCE=10; RETAIL_ITALY=11; RETAIL_IBERIA=12
COLLECT_NORTH=13; COLLECT_CENTRAL=14; COLLECT_SOUTH=15
EXIT_ROTTERDAM=16; EXIT_HAMBURG=17; EU_POOLER=18

NUM_NODES=18; N_0=60; SIMULATION_DAYS=365

DELAYS = {
    (1,3):1,(1,4):2,(2,3):2,(2,4):1,(2,5):3,(1,5):3,
    (3,8):1,(3,9):2,(4,9):1,(4,10):2,(4,8):2,(5,11):1,(5,12):2,(5,10):2,
    (8,13):2,(9,13):2,(9,14):2,(10,14):2,(10,15):3,(11,15):2,(12,15):2,
    (13,6):1,(14,6):2,(14,7):2,(15,7):1,
    (6,18):1,(7,18):1,(18,3):1,(18,4):1,(18,5):2,
    (18,16):1,(18,17):2,(16,1):14,(17,2):14,
}
TRANSPORT_COSTS = {
    (1,3):1.0,(1,4):2.5,(2,3):2.0,(2,4):1.5,(2,5):4.0,(1,5):4.5,
    (3,8):1.5,(3,9):2.5,(4,9):1.5,(4,10):3.0,(4,8):2.5,
    (5,11):1.5,(5,12):3.0,(5,10):2.5,
    (8,13):2.0,(9,13):2.5,(9,14):2.5,(10,14):2.0,(10,15):3.5,(11,15):2.0,(12,15):2.5,
    (13,6):1.0,(14,6):2.5,(14,7):2.5,(15,7):1.0,
    (6,18):0.5,(7,18):0.5,(18,3):1.0,(18,4):1.5,(18,5):2.5,
    (18,16):1.0,(18,17):1.5,(16,1):15.0,(17,2):15.0,
}
CARBON_EMISSIONS = {
    (1,3):0.3,(1,4):0.8,(2,3):0.6,(2,4):0.4,(2,5):1.5,(1,5):1.5,
    (3,8):0.4,(3,9):0.8,(4,9):0.4,(4,10):1.0,(4,8):0.8,
    (5,11):0.4,(5,12):1.0,(5,10):0.8,
    (8,13):0.6,(9,13):0.8,(9,14):0.8,(10,14):0.6,(10,15):1.2,(11,15):0.6,(12,15):0.8,
    (13,6):0.3,(14,6):0.8,(14,7):0.8,(15,7):0.3,
    (6,18):0.1,(7,18):0.1,(18,3):0.3,(18,4):0.5,(18,5):0.8,
    (18,16):0.3,(18,17):0.5,(16,1):12.0,(17,2):12.0,
}
HOLDING_COSTS = {
    1:0.20,2:0.20,3:0.15,4:0.15,5:0.15,6:0.12,7:0.12,
    8:0.08,9:0.08,10:0.08,11:0.08,12:0.08,
    13:0.10,14:0.10,15:0.10,16:0.18,17:0.18,18:0.10,
}
NODE_CAPACITY={i:150 for i in range(1,NUM_NODES+1)}; NODE_CAPACITY[18]=300
ARC_CAPACITY={e:60 for e in DELAYS}
PRODUCTION_COST=25.0; REPAIR_COST=8.0; WASHING_COST=1.5
C_MAX=12; MAX_WEAR=200; MAX_IDLE=20
WASH_CAPACITY={WASH_NORTH:30,WASH_SOUTH:25}; WASH_LEAD=2
P_DMG_TRANSIT=0.01; P_DMG_NODE=0.002
REPAIR_MEAN=10; REPAIR_STD=3; REPAIR_PROB=0.90

DC_TO_RETAIL={DC_NORTH:[RETAIL_BENELUX,RETAIL_GERMANY],DC_CENTRAL:[RETAIL_GERMANY,RETAIL_FRANCE,RETAIL_BENELUX],DC_SOUTH:[RETAIL_ITALY,RETAIL_IBERIA,RETAIL_FRANCE]}
RETAIL_TO_COLLECT={8:13,9:13,10:14,11:15,12:15}
RETAIL_DEMAND_BASE={8:5,9:7,10:6,11:5,12:4}

def get_eu_demand_multiplier(doy):
    if 305<=doy or doy<=90: return 2.0
    elif 91<=doy<=181: return 1.2
    elif 182<=doy<=243: return 0.5
    else: return 1.0

def get_dc_props(doy):
    m=get_eu_demand_multiplier(doy)
    if m>=1.5: return {3:0.35,4:0.40,5:0.25}
    elif m>=1.0: return {3:0.30,4:0.35,5:0.35}
    else: return {3:0.25,4:0.30,5:0.45}

@dataclass
class Package:
    id:int; position:int; cycle_count:int=0; max_cycles:int=C_MAX
    in_transit:bool=False; arrival_time:Optional[int]=None; next_position:Optional[int]=None
    retired:bool=False; forced_retirement:bool=False
    path_history:List[int]=field(default_factory=list)
    wear:float=0.0; idle_days:int=0; last_active:int=0
    hold_until:Optional[int]=None; hygiene:float=1.0; washes:int=0
    cost_transport:float=0.0; cost_carbon:float=0.0; cost_holding:float=0.0
    days_at_pos:int=0

class NetworkState:
    def __init__(self):
        self.inventory=np.zeros(NUM_NODES+1)
        self.flows=defaultdict(lambda:defaultdict(float))
        self.packages={}; self.retired_packages=[]
        self.time=0; self.total_produced=0; self.pkg_counter=N_0
        self.repair_backlog=[]; self.wash_queue={WASH_NORTH:[],WASH_SOUTH:[]}
        self.packages_being_washed=set()  # track pkg IDs currently in wash queue
        self.adjacency=np.zeros((NUM_NODES+1,NUM_NODES+1))
        for(i,j) in DELAYS: self.adjacency[i,j]=1
        for i in range(N_0):
            p=Package(id=i,position=EU_POOLER); p.path_history.append(EU_POOLER)
            self.packages[i]=p; self.inventory[EU_POOLER]+=1
        self.conservation_violations=[]
        self.total_transport_cost=0.0; self.total_carbon_emissions=0.0
        self.total_holding_cost=0.0; self.total_production_cost=0.0
        self.total_repair_cost=0.0; self.total_washing_cost=0.0
        self.daily_costs=[]

def sample_delay(i,j,doy):
    base=DELAYS.get((i,j),1); m=get_eu_demand_multiplier(doy)
    mean=base*(1.1 if m>1.5 else 1.0); std=max(0.5,0.2*base)
    s=int(max(1,round(np.random.normal(mean,std))))
    if random.random()<0.02: s+=random.randint(1,5)
    return s

def next_node(pkg,state,doy):
    p=pkg.position
    if p in[1,2]:
        props=get_dc_props(doy); return random.choices(list(props.keys()),weights=list(props.values()))[0]
    if p in DC_TO_RETAIL: return random.choice(DC_TO_RETAIL[p])
    if p in RETAIL_TO_COLLECT: return RETAIL_TO_COLLECT[p]
    if p==13: return WASH_NORTH
    if p==14: return random.choice([WASH_NORTH,WASH_SOUTH])
    if p==15: return WASH_SOUTH
    if p in[WASH_NORTH,WASH_SOUTH]: return EU_POOLER
    if p==EU_POOLER:
        if random.random()<0.8:
            props=get_dc_props(doy); return random.choices(list(props.keys()),weights=list(props.values()))[0]
        else: return random.choice([EXIT_ROTTERDAM,EXIT_HAMBURG])
    if p==EXIT_ROTTERDAM: return PORT_ROTTERDAM
    if p==EXIT_HAMBURG: return PORT_HAMBURG
    return None

def simulate_step(state,t):
    doy=t%365; mult=get_eu_demand_multiplier(doy)
    r_nat=np.zeros(NUM_NODES+1); r_frc=np.zeros(NUM_NODES+1); p_nat=np.zeros(NUM_NODES+1)
    dwc=0.0
    for wc in[WASH_NORTH,WASH_SOUTH]:
        still=[]; cap=WASH_CAPACITY[wc]; done=0
        for job in state.wash_queue[wc]:
            if t>=job['ready'] and done<cap:
                pid=job['pid']
                if pid in state.packages and not state.packages[pid].retired:
                    state.packages[pid].hygiene=1.0; state.packages[pid].washes+=1; done+=1; dwc+=WASHING_COST
                state.packages_being_washed.discard(pid)
            else: still.append(job)
        state.wash_queue[wc]=still
    state.total_washing_cost+=dwc
    refurb=0
    if state.repair_backlog:
        still=[]
        for job in state.repair_backlog:
            if t>=job['ready'] and random.random()<=REPAIR_PROB:
                np2=Package(id=state.pkg_counter,position=EU_POOLER)
                np2.path_history.append(EU_POOLER); np2.last_active=t
                state.packages[state.pkg_counter]=np2; state.pkg_counter+=1; refurb+=1
            else: still.append(job)
        state.repair_backlog=still
    if refurb: p_nat[EU_POOLER]+=refurb; state.total_repair_cost+=refurb*REPAIR_COST
    for pkg in list(state.packages.values()):
        if pkg.retired: continue
        wr=2.0 if mult>1.5 else(1.0 if mult>0.8 else 0.5); pkg.wear+=wr
        pkg.hygiene=max(0,pkg.hygiene-0.003)
        if pkg.cycle_count>=pkg.max_cycles or pkg.wear>=MAX_WEAR:
            pkg.retired=True; r_nat[pkg.position]+=1; state.retired_packages.append(pkg); continue
        if not pkg.in_transit and pkg.position==EU_POOLER:
            if pkg.last_active<t-1: pkg.idle_days+=1
            if pkg.idle_days>MAX_IDLE:
                pkg.retired=True; pkg.forced_retirement=True; r_frc[pkg.position]+=1; state.retired_packages.append(pkg)
    active=sum(1 for p in state.packages.values() if not p.retired)
    target=int(N_0*mult*0.9); prod=0
    if active<target: prod=min(target-active,20)
    pavail=sum(1 for p in state.packages.values() if p.position==EU_POOLER and not p.retired and not p.in_transit)
    thr=int(15*mult)
    if pavail<thr: prod+=max(0,min(thr-pavail,15))
    prod=min(prod,25)
    if prod>0:
        p_nat[EU_POOLER]+=prod; state.total_production_cost+=prod*PRODUCTION_COST
        for _ in range(prod):
            np2=Package(id=state.pkg_counter,position=EU_POOLER)
            np2.path_history.append(EU_POOLER); np2.last_active=t
            state.packages[state.pkg_counter]=np2; state.pkg_counter+=1; state.total_produced+=1
    nf=defaultdict(float); pbn=defaultdict(list)
    def _dispatch(pkg, node, n):
        """Dispatch pkg from node to n, respecting arc capacity. Returns True if dispatched."""
        arc=(node,n)
        if arc in ARC_CAPACITY and nf[arc]>=ARC_CAPACITY[arc]:
            return False
        pkg.in_transit=True; pkg.arrival_time=t+sample_delay(node,n,doy)
        pkg.next_position=n; pkg.last_active=t; nf[arc]+=1
        return True
    for pkg in state.packages.values():
        if not pkg.retired and not pkg.in_transit: pbn[pkg.position].append(pkg)
    rd={r:max(0,int(round(b*mult+np.random.normal(0,0.8)))) for r,b in RETAIL_DEMAND_BASE.items()}
    for node,pkgs in pbn.items():
        if 8<=node<=12:
            ready=[p for p in pkgs if p.hold_until is None or p.hold_until<=t]
            for pkg in ready:
                n=next_node(pkg,state,doy)
                if n: _dispatch(pkg,node,n)
            continue
        if node in[WASH_NORTH,WASH_SOUTH]:
            for pkg in pkgs:
                if pkg.hygiene<0.9 and pkg.id not in state.packages_being_washed:
                    state.wash_queue[node].append({'ready':t+WASH_LEAD,'pid':pkg.id})
                    state.packages_being_washed.add(pkg.id)
                elif pkg.hygiene>=0.9:
                    _dispatch(pkg,node,EU_POOLER)
            continue
        if node in[13,14,15]:
            batch=max(3,int(5*mult))
            if len(pkgs)>=batch:
                for pkg in pkgs[:batch*2]:
                    n=next_node(pkg,state,doy)
                    if n: _dispatch(pkg,node,n)
            continue
        if node in[16,17]:
            dow=t%7; sd=[1,4] if node==16 else [2,5]
            if dow in sd:
                for pkg in pkgs[:40]:
                    n=next_node(pkg,state,doy)
                    if n: _dispatch(pkg,node,n)
            continue
        if node in[3,4,5]:
            rets=DC_TO_RETAIL.get(node,[]); cap=sum(rd.get(r,0) for r in rets)
            for pkg in pkgs[:max(1,cap)]:
                n=next_node(pkg,state,doy)
                if n: _dispatch(pkg,node,n)
            continue
        dn=max(1,int(8*mult))
        for pkg in pkgs[:dn]:
            n=next_node(pkg,state,doy)
            if n:
                if _dispatch(pkg,node,n): pkg.idle_days=0
    state.flows[t]=dict(nf)
    arrivals=np.zeros(NUM_NODES+1)
    arrival_retirements=np.zeros(NUM_NODES+1)  # packages that arrive then immediately get damaged
    for pkg in list(state.packages.values()):
        if pkg.in_transit and not pkg.retired and pkg.arrival_time==t and pkg.next_position:
            dest=pkg.next_position; old=pkg.position
            if random.random()<P_DMG_TRANSIT:
                pkg.retired=True; pkg.forced_retirement=True; state.retired_packages.append(pkg)
                state.repair_backlog.append({'ready':t+int(max(1,round(np.random.normal(REPAIR_MEAN,REPAIR_STD)))),'pid':pkg.id})
                # Damaged in transit: does NOT arrive at destination, goes to repair
                pkg.in_transit=False; pkg.arrival_time=None; pkg.next_position=None
                continue
            tc=TRANSPORT_COSTS.get((old,dest),0); ce=CARBON_EMISSIONS.get((old,dest),0)
            pkg.cost_transport+=tc; pkg.cost_carbon+=ce; state.total_transport_cost+=tc; state.total_carbon_emissions+=ce
            arrivals[dest]+=1; pkg.position=dest; pkg.in_transit=False; pkg.arrival_time=None; pkg.next_position=None
            pkg.path_history.append(dest); pkg.days_at_pos=0
            if dest==EU_POOLER: pkg.cycle_count+=1
            if 8<=dest<=12: pkg.hold_until=t+int(max(1,round(np.random.normal(3 if mult>1.0 else 2,1))))
            pkg.hygiene=max(0,pkg.hygiene-0.01*DELAYS.get((old,dest),1))
            if not pkg.retired and random.random()<P_DMG_NODE:
                pkg.retired=True; pkg.forced_retirement=True; state.retired_packages.append(pkg)
                arrival_retirements[dest]+=1
    deps=np.zeros(NUM_NODES+1)
    for(i,j),f in nf.items(): deps[i]+=f
    ni=np.copy(state.inventory)+arrivals+p_nat-deps-r_nat-r_frc-arrival_retirements
    ni=np.maximum(ni,0)
    for i in range(1,NUM_NODES+1): ni[i]=min(ni[i],NODE_CAPACITY.get(i,150))
    state.inventory=ni
    dh=0.0
    for pkg in state.packages.values():
        if not pkg.retired:
            pkg.days_at_pos+=1; hc=HOLDING_COSTS.get(pkg.position,0.10); pkg.cost_holding+=hc; dh+=hc
    state.total_holding_cost+=dh
    state.daily_costs.append({'day':t,'transport_cost':sum(TRANSPORT_COSTS.get(e,0)*f for e,f in nf.items()),
        'holding_cost':dh,'production_cost':prod*PRODUCTION_COST if prod>0 else 0,
        'repair_cost':refurb*REPAIR_COST,'washing_cost':dwc})
    state.time=t; return state

def run_simulation(days=SIMULATION_DAYS):
    state=NetworkState()
    metrics={'time':[],'active_packages':[],'in_transit':[],'retired':[],'total_produced':[],
             'demand_multiplier':[],'node_inventory':defaultdict(list),'unmet_demand':[],'avg_hygiene':[]}
    for t in range(days):
        state=simulate_step(state,t)
        active=sum(1 for p in state.packages.values() if not p.retired)
        intrn=sum(1 for p in state.packages.values() if p.in_transit)
        ret=len(state.retired_packages); m=get_eu_demand_multiplier(t%365)
        hyg=[p.hygiene for p in state.packages.values() if not p.retired]
        metrics['time'].append(t); metrics['active_packages'].append(active)
        metrics['in_transit'].append(intrn); metrics['retired'].append(ret)
        metrics['total_produced'].append(state.total_produced); metrics['demand_multiplier'].append(m)
        metrics['unmet_demand'].append(0); metrics['avg_hygiene'].append(np.mean(hyg) if hyg else 0)
        for n in range(1,NUM_NODES+1):
            c=sum(1 for p in state.packages.values() if p.position==n and not p.in_transit and not p.retired)
            metrics['node_inventory'][n].append(c)
    return state,metrics

def get_node_name(nid):
    return {1:"Port-Rotterdam",2:"Port-Hamburg",3:"DC-North",4:"DC-Central",5:"DC-South",
        6:"Wash-North",7:"Wash-South",8:"Retail-Benelux",9:"Retail-Germany",10:"Retail-France",
        11:"Retail-Italy",12:"Retail-Iberia",13:"Collect-North",14:"Collect-Central",15:"Collect-South",
        16:"Exit-Rotterdam",17:"Exit-Hamburg",18:"EU-Pooler"}.get(nid,f"Node-{nid}")

def export_for_visualization(state,metrics,filename='eu_regional_simulation_data.json'):
    node_info={
        1:{"name":"Port Rotterdam","type":"port","icon":"🚢","region":"North"},
        2:{"name":"Port Hamburg","type":"port","icon":"🚢","region":"North"},
        3:{"name":"DC North (NL/BE)","type":"dc","icon":"📦","region":"North"},
        4:{"name":"DC Central (DE/FR)","type":"dc","icon":"📦","region":"Central"},
        5:{"name":"DC South (IT/ES)","type":"dc","icon":"📦","region":"South"},
        6:{"name":"Wash Center North","type":"wash","icon":"🧼","region":"North"},
        7:{"name":"Wash Center South","type":"wash","icon":"🧼","region":"South"},
        8:{"name":"Retail Benelux","type":"retail","icon":"🏪","region":"North"},
        9:{"name":"Retail Germany","type":"retail","icon":"🏪","region":"Central"},
        10:{"name":"Retail France","type":"retail","icon":"🏪","region":"Central"},
        11:{"name":"Retail Italy","type":"retail","icon":"🏪","region":"South"},
        12:{"name":"Retail Iberia","type":"retail","icon":"🏪","region":"South"},
        13:{"name":"Collection North","type":"collect","icon":"♻️","region":"North"},
        14:{"name":"Collection Central","type":"collect","icon":"♻️","region":"Central"},
        15:{"name":"Collection South","type":"collect","icon":"♻️","region":"South"},
        16:{"name":"Exit Rotterdam","type":"exit_port","icon":"🚢","region":"North"},
        17:{"name":"Exit Hamburg","type":"exit_port","icon":"🚢","region":"North"},
        18:{"name":"EU Pooler","type":"pooler","icon":"🏭","region":"Central"},
    }
    edges=[{"source":i,"target":j,"delay":d,"cost":TRANSPORT_COSTS.get((i,j),0),
            "carbon":CARBON_EMISSIONS.get((i,j),0),"ocean":(i in[16,17] and j in[1,2])} for(i,j),d in DELAYS.items()]
    daily_data=[]; cT=cH=cP=cR=cW=0
    for t in range(len(metrics['time'])):
        doy=t%365
        season="high_import" if(305<=doy or doy<=90) else("medium" if 91<=doy<=181 else("low" if 182<=doy<=243 else "rising"))
        ni={str(n):metrics['node_inventory'][n][t] for n in range(1,NUM_NODES+1)}
        fl=[{"source":i,"target":j,"count":int(f)} for(i,j),f in state.flows[t].items() if f>0] if t in state.flows else []
        dc=state.daily_costs[t] if t<len(state.daily_costs) else {}
        cT+=dc.get('transport_cost',0); cH+=dc.get('holding_cost',0); cP+=dc.get('production_cost',0)
        cR+=dc.get('repair_cost',0); cW+=dc.get('washing_cost',0)
        daily_data.append({"day":t,"day_of_year":doy,"season":season,
            "demand_multiplier":metrics['demand_multiplier'][t],
            "active_packages":metrics['active_packages'][t],"in_transit":metrics['in_transit'][t],
            "retired":metrics['retired'][t],"total_produced":metrics['total_produced'][t],
            "avg_hygiene":round(metrics['avg_hygiene'][t],4),
            "node_inventories":ni,"flows":fl,
            "transport_cost":dc.get('transport_cost',0),"holding_cost":dc.get('holding_cost',0),
            "production_cost":dc.get('production_cost',0),"repair_cost":dc.get('repair_cost',0),
            "washing_cost":dc.get('washing_cost',0),
            "cum_transport":round(cT,2),"cum_holding":round(cH,2),"cum_production":round(cP,2),
            "cum_repair":round(cR,2),"cum_washing":round(cW,2)})
    data={"config":{"initial_packages":N_0,"num_nodes":NUM_NODES,"simulation_days":len(metrics['time']),
        "model_name":"EU Multi-Echelon Regional Distribution with Washing"},
        "nodes":node_info,"edges":edges,"daily_data":daily_data,
        "totals":{"transport_cost":state.total_transport_cost,"holding_cost":state.total_holding_cost,
            "production_cost":state.total_production_cost,"repair_cost":state.total_repair_cost,
            "washing_cost":state.total_washing_cost,"carbon_emissions":state.total_carbon_emissions}}
    with open(filename,'w') as f: json.dump(data,f,indent=2)
    print(f"  ✓ Exported: {filename}"); return filename

if __name__=="__main__":
    print("="*70); print("EU MULTI-ECHELON REGIONAL DISTRIBUTION WITH WASHING MODEL"); print("="*70)
    random.seed(42); np.random.seed(42); print("Running simulation...")
    state,metrics=run_simulation()
    tc=state.total_transport_cost+state.total_holding_cost+state.total_production_cost+state.total_repair_cost+state.total_washing_cost
    print(f"  Active: {metrics['active_packages'][-1]}"); print(f"  Retired: {metrics['retired'][-1]}")
    print(f"  Produced: {state.total_produced}"); print(f"  Total Cost: ${tc:,.2f}")
    print(f"  Washing Cost: ${state.total_washing_cost:,.2f}"); print(f"  Total CO2: {state.total_carbon_emissions:,.1f} kg")
    export_for_visualization(state,metrics); print("Done!")
