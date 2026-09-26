import networkx as nx
from pyvis.network import Network


def create_dependency_graph(dependencies, filename="dependency_graph.html"):
    G = nx.DiGraph()

    for function_name, called_functions in dependencies.items():
        G.add_node(
            function_name,
            label=function_name,
            title=f"Caller Function: {function_name}",
            shape="box",
            color={
                'background': '#6366f1',
                'border': '#818cf8',
                'highlight': {'background': '#4f46e5', 'border': '#a5b4fc'},
                'hover': {'background': '#4f46e5', 'border': '#a5b4fc'}
            },
            font={'color': '#ffffff', 'face': 'Inter, system-ui, sans-serif', 'size': 13, 'style': 'bold'},
            margin=10,
            borderWidth=1.5,
            shadow={'enabled': True, 'color': 'rgba(0,0,0,0.5)', 'size': 6}
        )

        for called_function in called_functions:
            G.add_node(
                called_function,
                label=called_function,
                title=f"Dependency Function: {called_function}",
                shape="box",
                color={
                    'background': '#0284c7',
                    'border': '#38bdf8',
                    'highlight': {'background': '#0369a1', 'border': '#7dd3fc'},
                    'hover': {'background': '#0369a1', 'border': '#7dd3fc'}
                },
                font={'color': '#ffffff', 'face': 'Inter, system-ui, sans-serif', 'size': 12},
                margin=8,
                borderWidth=1.5,
                shadow={'enabled': True, 'color': 'rgba(0,0,0,0.4)', 'size': 4}
            )

            G.add_edge(
                function_name,
                called_function,
                color={'color': '#475569', 'highlight': '#38bdf8', 'hover': '#38bdf8', 'opacity': 0.85},
                width=2,
                arrows={'to': {'enabled': True, 'scaleFactor': 0.8}}
            )

    net = Network(
        height="750px",
        width="100%",
        directed=True,
        bgcolor="#0b0f19",
        font_color="#f8fafc"
    )

    net.from_nx(G)
    net.set_options("""
    var options = {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.01,
          "springLength": 100,
          "springConstant": 0.08
        },
        "maxVelocity": 50,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": { "iterations": 150 }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100
      }
    }
    """)
    net.write_html(str(filename))


def create_impact_graph(
    changed_function,
    direct_impact,
    indirect_impact,
    reverse_dependencies,
    filename="impact_graph.html"
):
    G = nx.DiGraph()

    G.add_node(
        changed_function,
        label=f"🔥 {changed_function}",
        title=f"Changed Function (Root Risk): {changed_function}",
        shape="box",
        color={
            'background': '#e11d48',
            'border': '#f43f5e',
            'highlight': {'background': '#be123c', 'border': '#fb7185'},
            'hover': {'background': '#be123c', 'border': '#fb7185'}
        },
        font={'color': '#ffffff', 'face': 'Inter, system-ui, sans-serif', 'size': 14, 'style': 'bold'},
        margin=12,
        borderWidth=2,
        shadow={'enabled': True, 'color': 'rgba(225, 29, 72, 0.4)', 'size': 10}
    )

    # Changed function → Direct impact
    for function in direct_impact:
        G.add_node(
            function,
            label=function,
            title=f"Directly Impacted Function: {function}",
            shape="box",
            color={
                'background': '#d97706',
                'border': '#fbbf24',
                'highlight': {'background': '#b45309', 'border': '#fde047'},
                'hover': {'background': '#b45309', 'border': '#fde047'}
            },
            font={'color': '#ffffff', 'face': 'Inter, system-ui, sans-serif', 'size': 13, 'style': 'bold'},
            margin=9,
            borderWidth=1.5,
            shadow={'enabled': True, 'color': 'rgba(217, 119, 6, 0.3)', 'size': 6}
        )

        G.add_edge(
            changed_function,
            function,
            color={'color': '#f59e0b', 'highlight': '#fde047', 'hover': '#fde047'},
            width=2.5,
            arrows={'to': {'enabled': True, 'scaleFactor': 0.8}}
        )

    # Direct impact → Indirect impact
    for function in direct_impact:
        for caller in reverse_dependencies.get(function, []):
            if caller in indirect_impact:
                G.add_node(
                    caller,
                    label=caller,
                    title=f"Indirectly Impacted Caller: {caller}",
                    shape="box",
                    color={
                        'background': '#059669',
                        'border': '#34d399',
                        'highlight': {'background': '#047857', 'border': '#6ee7b7'},
                        'hover': {'background': '#047857', 'border': '#6ee7b7'}
                    },
                    font={'color': '#ffffff', 'face': 'Inter, system-ui, sans-serif', 'size': 12},
                    margin=8,
                    borderWidth=1.5,
                    shadow={'enabled': True, 'color': 'rgba(5, 150, 105, 0.3)', 'size': 5}
                )

                G.add_edge(
                    function,
                    caller,
                    color={'color': '#10b981', 'highlight': '#34d399', 'hover': '#34d399'},
                    width=2,
                    arrows={'to': {'enabled': True, 'scaleFactor': 0.8}}
                )

    net = Network(
        height="750px",
        width="100%",
        directed=True,
        bgcolor="#0b0f19",
        font_color="#f8fafc"
    )

    net.from_nx(G)
    net.set_options("""
    var options = {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.01,
          "springLength": 100,
          "springConstant": 0.08
        },
        "maxVelocity": 50,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": { "iterations": 150 }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100
      }
    }
    """)
    net.write_html(str(filename))