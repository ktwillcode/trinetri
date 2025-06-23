#!/usr/bin/env python3
"""
Trinetri LangGraph Demo Cookbook - Two Agent System
==================================================

This demo showcases a complete multi-agent workflow with:
- Planner Agent: Creates research plans
- Researcher Agent: Executes research tasks
- Full tracing with correlation IDs, agent IDs, and step IDs
- Evaluation gating with custom metrics

Run with:
    python examples/demo_langgraph.py
"""

import trinetri_auto  # 🎯 Auto-instruments everything!

import os
import sys
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from trinetri_auto.eval import score_with
from trinetri_auto._ids import correlation_id, agent_id, step_id

# Configure environment if not set
if not os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT'):
    os.environ['OTEL_EXPORTER_OTLP_ENDPOINT'] = 'http://localhost:4318'
if not os.getenv('OTEL_SERVICE_NAME'):
    os.environ['OTEL_SERVICE_NAME'] = 'trinetri-cookbook-demo'

print("🎯 Trinetri LangGraph Demo Cookbook")
print("=" * 50)
print(f"🔗 OTLP Endpoint: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')}")
print(f"🏷️  Service Name: {os.getenv('OTEL_SERVICE_NAME')}")
print()

class CookbookState(TypedDict):
    """State that flows between our cookbook agents"""
    research_topic: str
    plan: str
    research_findings: List[str]
    final_summary: str
    workflow_metadata: dict

def print_trace_ids(agent_name: str, operation: str) -> dict:
    """Print current trace IDs for demonstration"""
    current_correlation = correlation_id()
    current_agent = agent_id() 
    current_step = step_id()
    
    metadata = {
        "agent_name": agent_name,
        "operation": operation,
        "correlation_id": current_correlation,
        "agent_id": current_agent,
        "step_id": current_step
    }
    
    print(f"📍 {agent_name} - {operation}")
    print(f"   🔗 correlation_id: {current_correlation}")
    print(f"   🤖 agent_id: {current_agent}")
    print(f"   📋 step_id: {current_step}")
    print()
    
    return metadata

# 📋 Planner Agent with Quality Evaluation
def planner_quality_check(input_text: str, output_text: str) -> float:
    """
    Custom evaluation for plan quality
    Checks for structure, specificity, and actionability
    """
    score = 0.0
    
    # Check for structured plan
    if "step" in output_text.lower() or "phase" in output_text.lower():
        score += 0.3
    
    # Check for specific details
    if len(output_text.split()) > 30:  # Detailed plan
        score += 0.3
    
    # Check for research methodology
    if "source" in output_text.lower() or "method" in output_text.lower():
        score += 0.4
    
    return min(score, 1.0)

@score_with(metric=planner_quality_check, threshold=0.8)
def planner_agent(state: CookbookState) -> CookbookState:
    """
    🧠 Planner Agent: Creates comprehensive research plans
    Includes evaluation gating to ensure plan quality
    """
    
    # Print trace IDs for demo
    trace_metadata = print_trace_ids("Planner Agent", "Plan Creation")
    
    topic = state["research_topic"]
    
    # Simulate planning work (replace with your LLM call)
    research_plan = f"""
    📋 COMPREHENSIVE RESEARCH PLAN for '{topic}'
    
    PHASE 1: Background Research
    - Step 1.1: Review existing literature and studies
    - Step 1.2: Identify key stakeholders and experts
    - Step 1.3: Analyze current market trends
    
    PHASE 2: Primary Research
    - Step 2.1: Conduct expert interviews (3-5 specialists)
    - Step 2.2: Survey relevant practitioners (50+ responses)
    - Step 2.3: Analyze case studies from leading organizations
    
    PHASE 3: Data Analysis
    - Step 3.1: Synthesize quantitative findings
    - Step 3.2: Extract qualitative insights
    - Step 3.3: Identify patterns and correlations
    
    RESEARCH METHODS:
    - Academic source analysis
    - Industry report review
    - Statistical data gathering
    - Expert consultation methodology
    
    DELIVERABLES:
    - Comprehensive findings report
    - Executive summary with recommendations
    - Supporting data visualizations
    
    QUALITY ASSURANCE:
    - Peer review of methodology
    - Source verification and validation
    - Bias analysis and mitigation
    """
    
    print(f"✅ Plan created for topic: {topic}")
    print(f"📊 Plan quality score will be evaluated...")
    print()
    
    # Update workflow metadata
    workflow_metadata = state.get("workflow_metadata", {})
    workflow_metadata["planner_trace"] = trace_metadata
    
    return {
        "research_topic": topic,
        "plan": research_plan,
        "research_findings": state.get("research_findings", []),
        "final_summary": state.get("final_summary", ""),
        "workflow_metadata": workflow_metadata
    }

# 🔬 Researcher Agent with Thoroughness Evaluation  
def research_thoroughness_check(input_text: str, output_text: str) -> float:
    """
    Custom evaluation for research thoroughness
    Checks for depth, breadth, and source diversity
    """
    score = 0.0
    
    # Check for multiple findings
    if output_text.count("Finding") >= 3:
        score += 0.25
    
    # Check for diverse sources
    if "study" in output_text.lower() and "report" in output_text.lower():
        score += 0.25
    
    # Check for quantitative data
    if any(char.isdigit() for char in output_text):
        score += 0.25
    
    # Check for conclusions
    if "conclusion" in output_text.lower() or "summary" in output_text.lower():
        score += 0.25
    
    return min(score, 1.0)

@score_with(metric=research_thoroughness_check, threshold=0.75)
def researcher_agent(state: CookbookState) -> CookbookState:
    """
    🔬 Researcher Agent: Executes the research plan
    Includes evaluation to ensure research thoroughness
    """
    
    # Print trace IDs for demo
    trace_metadata = print_trace_ids("Researcher Agent", "Research Execution")
    
    topic = state["research_topic"]
    plan = state["plan"]
    
    # Simulate research execution (replace with your LLM calls)
    research_findings = [
        f"""
        🔍 FINDING 1: Literature Analysis for '{topic}'
        
        Academic studies from 2023-2024 show significant advances in this field.
        Key study by Johnson et al. (2024) demonstrates 67% improvement in efficiency.
        Meta-analysis of 15 papers reveals consistent patterns across implementations.
        
        Sources: Journal of Advanced Research, Tech Innovation Quarterly
        Confidence Level: High (85%)
        """,
        
        f"""
        🔍 FINDING 2: Industry Report Analysis for '{topic}'
        
        Market research indicates 340% growth in adoption over past 18 months.
        Leading companies report average ROI of 245% within first year.
        Survey of 127 practitioners shows 89% satisfaction rate.
        
        Sources: Industry Analytics Report 2024, Professional Survey Data
        Confidence Level: Very High (92%)
        """,
        
        f"""
        🔍 FINDING 3: Expert Interview Insights for '{topic}'
        
        Consensus among 5 industry experts interviewed:
        - Technology maturity has reached inflection point
        - Best practices are now well-established
        - Main barrier is organizational change management (67% cite this)
        
        Sources: Direct expert interviews, Professional network consultation
        Confidence Level: High (88%)
        """,
        
        f"""
        🔍 FINDING 4: Case Study Analysis for '{topic}'
        
        Detailed analysis of 8 successful implementations shows:
        - Average implementation time: 4.2 months
        - Success factors: Executive support (100%), Training (85%), Phased approach (92%)
        - Common pitfalls: Insufficient planning (45%), Resource constraints (38%)
        
        Sources: Company case studies, Implementation documentation
        Confidence Level: High (83%)
        """
    ]
    
    print(f"✅ Research completed for topic: {topic}")
    print(f"📊 Found {len(research_findings)} key findings")
    print(f"🎯 Research thoroughness will be evaluated...")
    print()
    
    # Update workflow metadata
    workflow_metadata = state.get("workflow_metadata", {})
    workflow_metadata["researcher_trace"] = trace_metadata
    
    return {
        "research_topic": topic,
        "plan": plan,
        "research_findings": research_findings,
        "final_summary": state.get("final_summary", ""),
        "workflow_metadata": workflow_metadata
    }

def summarizer_agent(state: CookbookState) -> CookbookState:
    """
    📊 Summarizer Agent: Creates final executive summary
    No evaluation - final step in the workflow
    """
    
    # Print trace IDs for demo
    trace_metadata = print_trace_ids("Summarizer Agent", "Summary Generation")
    
    topic = state["research_topic"]
    findings = state["research_findings"]
    
    # Create executive summary
    summary = f"""
    🎯 EXECUTIVE SUMMARY: {topic}
    
    RESEARCH OVERVIEW:
    Comprehensive analysis conducted across multiple dimensions including academic literature,
    industry reports, expert interviews, and case study analysis.
    
    KEY INSIGHTS:
    • Academic research shows 67% efficiency improvements (high confidence)
    • Market growth of 340% over 18 months indicates strong adoption
    • Expert consensus confirms technology maturity and established best practices
    • Case studies reveal 4.2 month average implementation with clear success factors
    
    QUANTITATIVE HIGHLIGHTS:
    • 245% average ROI within first year
    • 89% practitioner satisfaction rate  
    • 92% success rate with phased implementation approach
    • 100% correlation between executive support and project success
    
    RECOMMENDATIONS:
    1. IMMEDIATE: Begin planning phase with executive sponsorship
    2. SHORT-TERM: Implement phased approach with comprehensive training
    3. LONG-TERM: Focus on change management and resource allocation
    
    RISK MITIGATION:
    • Address planning gaps early (45% failure factor)
    • Ensure adequate resource allocation (38% constraint factor)
    • Maintain executive support throughout implementation
    
    CONFIDENCE LEVEL: High (87% overall)
    DATA SOURCES: {len(findings)} primary research streams
    RESEARCH QUALITY: Validated through multiple methodologies
    
    STATUS: ✅ RESEARCH COMPLETE - READY FOR DECISION MAKING
    """
    
    print(f"✅ Executive summary generated for: {topic}")
    print(f"📋 Summary includes insights from {len(findings)} research streams")
    print()
    
    # Update workflow metadata
    workflow_metadata = state.get("workflow_metadata", {})
    workflow_metadata["summarizer_trace"] = trace_metadata
    
    return {
        "research_topic": topic,
        "plan": state["plan"],
        "research_findings": findings,
        "final_summary": summary,
        "workflow_metadata": workflow_metadata
    }

def should_continue(state: CookbookState) -> str:
    """Route the workflow based on current state"""
    if not state.get("plan"):
        return "planner"
    elif not state.get("research_findings"):
        return "researcher"  
    elif not state.get("final_summary"):
        return "summarizer"
    else:
        return END

def main():
    """Execute the complete cookbook demo workflow"""
    
    print("🚀 Starting Trinetri Cookbook Demo...")
    print("📡 All operations will be traced with correlation IDs")
    print("🎯 Evaluation gates will ensure quality at each step")
    print()
    
    # Build the workflow graph
    cookbook_workflow = StateGraph(CookbookState)
    
    # Add our cookbook agents
    cookbook_workflow.add_node("planner", planner_agent)
    cookbook_workflow.add_node("researcher", researcher_agent)
    cookbook_workflow.add_node("summarizer", summarizer_agent)
    
    # Define the workflow routing
    cookbook_workflow.set_entry_point("planner")
    cookbook_workflow.add_edge("planner", "researcher")
    cookbook_workflow.add_edge("researcher", "summarizer")
    cookbook_workflow.add_edge("summarizer", END)
    
    # Compile the cookbook
    cookbook_app = cookbook_workflow.compile()
    
    # Define our research topic
    research_topic = "Multi-Agent AI System Optimization and Best Practices"
    
    # Initial state
    initial_state = {
        "research_topic": research_topic,
        "plan": "",
        "research_findings": [],
        "final_summary": "",
        "workflow_metadata": {}
    }
    
    try:
        print(f"🎬 Executing cookbook workflow for: {research_topic}")
        print("=" * 80)
        print()
        
        # Execute the workflow with full tracing
        result = cookbook_app.invoke(initial_state)
        
        print("=" * 80)
        print("🎉 COOKBOOK DEMO COMPLETED SUCCESSFULLY!")
        print()
        
        # Display workflow metadata with trace IDs
        print("📊 WORKFLOW TRACE SUMMARY:")
        print("-" * 40)
        
        for agent_name, trace_data in result["workflow_metadata"].items():
            if isinstance(trace_data, dict):
                print(f"🤖 {trace_data.get('agent_name', 'Unknown Agent')}")
                print(f"   Operation: {trace_data.get('operation', 'Unknown')}")
                print(f"   Correlation: {trace_data.get('correlation_id', 'N/A')}")
                print(f"   Agent ID: {trace_data.get('agent_id', 'N/A')}")
                print(f"   Step ID: {trace_data.get('step_id', 'N/A')}")
                print()
        
        # Display final results
        print("📋 FINAL DELIVERABLE:")
        print("-" * 40)
        print(result["final_summary"][:500] + "...")
        print()
        
        print("🎯 KEY ACCOMPLISHMENTS:")
        print("✅ Multi-agent workflow executed successfully")
        print("✅ All evaluation gates passed (quality assured)")
        print("✅ Complete trace correlation maintained")
        print("✅ Comprehensive research findings generated")
        print()
        
        print("📡 OBSERVABILITY:")
        print(f"✅ Traces available in Grafana: http://localhost:3000")
        print(f"✅ Service: {os.getenv('OTEL_SERVICE_NAME')}")
        print(f"✅ Endpoint: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')}")
        
    except Exception as e:
        print(f"❌ Cookbook demo failed: {e}")
        print("💡 Check your OTEL configuration and Grafana setup")
        print("🔧 Run 'trinetri doctor' to validate your environment")
        sys.exit(1)

if __name__ == "__main__":
    main() 