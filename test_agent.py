import sys
sys.path.insert(0, 'c:/Users/brand/OneDrive/Desktop/nse-scheduler-backend/ai-service')
from services.efficiency_agent import infer_efficiency

result = infer_efficiency(
    project_type='Office Tenant Improvement',
    budgeted_hrs=1200,
    supervisor='Joe Lawhorn',
)
print(f'Inferred efficiency: {result.inferredEfficiency}')
print(f'Confidence:          {result.confidence}')
print(f'Matches found:       {result.matchCount}')
print(f'Warning:             {result.warning}')
print()
for e in result.evidence:
    print(f"  {e['jobNumber']} | {e['jobName']} | eff={e['actualEfficiency']} | score={e['similarityScore']}")
