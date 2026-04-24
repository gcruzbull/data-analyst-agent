from src.agent.agent_graph import run_agent

question = "¿Cuál es el producto más vendido?"

response = run_agent(question)

print("\nRespuesta del agente:\n")
print(response)