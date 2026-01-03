# Forge V3 - Phase 7: User Interfaces

**Purpose:** Implement CLI, Web Dashboard, and Mobile App interfaces.

**Estimated Effort:** 5-7 days
**Dependencies:** Phase 0-6 (API must be complete)
**Outputs:** Three interface options for users to interact with Forge

---

## 1. Overview

Forge provides three interfaces:
- **CLI** - For developers and power users (Typer + Rich)
- **Web Dashboard** - Primary interface (React + Shadcn/UI)
- **Mobile App** - Quick monitoring and voting (React Native)

---

## 2. Command Line Interface

### 2.1 CLI Structure

```python
# cli/forge_cli/main.py
"""
Forge CLI - Command line interface for Forge operations.

Usage:
    forge auth login
    forge capsule create --content "..." --type knowledge
    forge capsule search "query"
    forge governance vote <proposal_id> for
"""
import typer
from rich.console import Console
from rich.table import Table

from forge_cli.auth import app as auth_app
from forge_cli.capsule import app as capsule_app
from forge_cli.governance import app as governance_app
from forge_cli.config import get_config

console = Console()
app = typer.Typer(
    name="forge",
    help="Forge Cascade CLI - Institutional Memory Engine",
    no_args_is_help=True,
)

# Register sub-commands
app.add_typer(auth_app, name="auth")
app.add_typer(capsule_app, name="capsule")
app.add_typer(governance_app, name="governance")


@app.command()
def version():
    """Show CLI version."""
    console.print("[bold blue]Forge CLI[/bold blue] v3.0.0")


@app.command()
def status():
    """Show connection status and current user."""
    config = get_config()
    
    if config.access_token:
        console.print(f"[green]✓[/green] Logged in as: {config.email}")
        console.print(f"  API: {config.api_url}")
    else:
        console.print("[yellow]Not logged in[/yellow]")
        console.print(f"  API: {config.api_url}")


if __name__ == "__main__":
    app()
```

### 2.2 Auth Commands

```python
# cli/forge_cli/auth.py
"""
Authentication commands.
"""
import typer
from rich.console import Console
from rich.prompt import Prompt

from forge_cli.api import ForgeAPI
from forge_cli.config import save_credentials, clear_credentials, get_config

console = Console()
app = typer.Typer(help="Authentication commands")


@app.command()
def login(
    email: str = typer.Option(None, "--email", "-e", help="Email address"),
    password: str = typer.Option(None, "--password", "-p", help="Password (not recommended)"),
):
    """Login to Forge."""
    # Prompt for missing credentials
    if not email:
        email = Prompt.ask("Email")
    if not password:
        password = Prompt.ask("Password", password=True)
    
    api = ForgeAPI()
    
    with console.status("Authenticating..."):
        try:
            result = api.login(email, password)
            save_credentials(
                access_token=result["access_token"],
                refresh_token=result["refresh_token"],
                email=email,
            )
            console.print(f"[green]✓[/green] Logged in as {email}")
        except Exception as e:
            console.print(f"[red]✗[/red] Login failed: {e}")
            raise typer.Exit(1)


@app.command()
def logout():
    """Logout and clear stored credentials."""
    config = get_config()
    
    if config.access_token:
        api = ForgeAPI()
        try:
            api.logout()
        except Exception:
            pass  # Ignore errors during logout
    
    clear_credentials()
    console.print("[green]✓[/green] Logged out")


@app.command()
def whoami():
    """Show current user information."""
    api = ForgeAPI()
    
    try:
        user = api.get_current_user()
        
        console.print(f"[bold]Email:[/bold] {user['email']}")
        console.print(f"[bold]Trust Level:[/bold] {user['trust_level']}")
        console.print(f"[bold]Roles:[/bold] {', '.join(user['roles'])}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to get user info: {e}")
        raise typer.Exit(1)
```

### 2.3 Capsule Commands

```python
# cli/forge_cli/capsule.py
"""
Capsule management commands.
"""
from pathlib import Path
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel

from forge_cli.api import ForgeAPI

console = Console()
app = typer.Typer(help="Capsule management commands")


@app.command("list")
def list_capsules(
    page: int = typer.Option(1, "--page", "-p"),
    limit: int = typer.Option(20, "--limit", "-l"),
    type: str = typer.Option(None, "--type", "-t", help="Filter by type"),
):
    """List capsules."""
    api = ForgeAPI()
    
    with console.status("Fetching capsules..."):
        result = api.list_capsules(page=page, per_page=limit, type=type)
    
    capsules = result["data"]
    
    if not capsules:
        console.print("[yellow]No capsules found[/yellow]")
        return
    
    table = Table(title="Capsules")
    table.add_column("ID", style="dim")
    table.add_column("Type")
    table.add_column("Trust")
    table.add_column("Content Preview")
    table.add_column("Created")
    
    for c in capsules:
        content_preview = c["content"][:50] + "..." if len(c["content"]) > 50 else c["content"]
        table.add_row(
            c["id"][:8],
            c["type"],
            c["trust_level"],
            content_preview,
            c["created_at"][:10],
        )
    
    console.print(table)
    console.print(f"\nPage {result['meta']['page']} of {result['meta']['pages']}")


@app.command("get")
def get_capsule(capsule_id: str):
    """Get capsule details."""
    api = ForgeAPI()
    
    with console.status("Fetching capsule..."):
        result = api.get_capsule(capsule_id)
    
    capsule = result["data"]
    
    console.print(Panel(
        f"[bold]ID:[/bold] {capsule['id']}\n"
        f"[bold]Type:[/bold] {capsule['type']}\n"
        f"[bold]Trust Level:[/bold] {capsule['trust_level']}\n"
        f"[bold]Version:[/bold] {capsule['version']}\n"
        f"[bold]Created:[/bold] {capsule['created_at']}",
        title="Capsule Details",
    ))
    
    # Show content
    content = capsule["content"]
    if capsule["type"] == "code":
        console.print(Syntax(content, "python", theme="monokai"))
    else:
        console.print(Panel(content, title="Content"))


@app.command("create")
def create_capsule(
    content: str = typer.Option(None, "--content", "-c", help="Capsule content"),
    file: Path = typer.Option(None, "--file", "-f", help="Read content from file"),
    type: str = typer.Option("knowledge", "--type", "-t", help="Capsule type"),
    parent: str = typer.Option(None, "--parent", "-p", help="Parent capsule ID"),
):
    """Create a new capsule."""
    # Get content from file or argument
    if file:
        if not file.exists():
            console.print(f"[red]✗[/red] File not found: {file}")
            raise typer.Exit(1)
        content = file.read_text()
    
    if not content:
        console.print("[red]✗[/red] Content required (--content or --file)")
        raise typer.Exit(1)
    
    api = ForgeAPI()
    
    with console.status("Creating capsule..."):
        result = api.create_capsule(
            content=content,
            type=type,
            parent_id=parent,
        )
    
    capsule = result["data"]
    console.print(f"[green]✓[/green] Created capsule: {capsule['id']}")


@app.command("search")
def search_capsules(
    query: str,
    limit: int = typer.Option(10, "--limit", "-l"),
):
    """Semantic search for capsules."""
    api = ForgeAPI()
    
    with console.status(f"Searching for '{query}'..."):
        result = api.search_capsules(query=query, limit=limit)
    
    results = result["data"]
    
    if not results:
        console.print("[yellow]No results found[/yellow]")
        return
    
    table = Table(title=f"Search Results for '{query}'")
    table.add_column("Score", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Type")
    table.add_column("Content Preview")
    
    for r in results:
        c = r["capsule"]
        preview = c["content"][:60] + "..." if len(c["content"]) > 60 else c["content"]
        table.add_row(
            f"{r['score']:.2f}",
            c["id"][:8],
            c["type"],
            preview,
        )
    
    console.print(table)


@app.command("lineage")
def show_lineage(capsule_id: str, depth: int = typer.Option(10, "--depth", "-d")):
    """Show capsule ancestry (Isnad)."""
    api = ForgeAPI()
    
    with console.status("Fetching lineage..."):
        result = api.get_lineage(capsule_id, max_depth=depth)
    
    lineage = result["data"]["lineage"]
    
    if not lineage:
        console.print("[yellow]No ancestors found[/yellow]")
        return
    
    console.print(f"[bold]Lineage for {capsule_id[:8]}[/bold]\n")
    
    for entry in lineage:
        c = entry["capsule"]
        indent = "  " * entry["depth"]
        console.print(f"{indent}↑ [{c['type']}] {c['id'][:8]}: {c['content'][:40]}...")
```

### 2.4 Governance Commands

```python
# cli/forge_cli/governance.py
"""
Governance commands for proposals and voting.
"""
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

from forge_cli.api import ForgeAPI

console = Console()
app = typer.Typer(help="Governance commands")


@app.command("proposals")
def list_proposals(
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    page: int = typer.Option(1, "--page", "-p"),
):
    """List governance proposals."""
    api = ForgeAPI()
    
    with console.status("Fetching proposals..."):
        result = api.list_proposals(status=status, page=page)
    
    proposals = result["data"]
    
    if not proposals:
        console.print("[yellow]No proposals found[/yellow]")
        return
    
    table = Table(title="Governance Proposals")
    table.add_column("ID", style="dim")
    table.add_column("Status")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Votes (For/Against)")
    
    for p in proposals:
        status_color = {
            "active": "green",
            "draft": "yellow",
            "approved": "blue",
            "rejected": "red",
        }.get(p["status"], "white")
        
        table.add_row(
            p["id"][:8],
            f"[{status_color}]{p['status']}[/{status_color}]",
            p["type"],
            p["title"][:40],
            f"{p['votes_for']:.1f} / {p['votes_against']:.1f}",
        )
    
    console.print(table)


@app.command("vote")
def cast_vote(
    proposal_id: str,
    decision: str = typer.Argument(..., help="Vote decision: for, against, or abstain"),
    reason: str = typer.Option(None, "--reason", "-r", help="Optional reasoning"),
):
    """Cast a vote on a proposal."""
    if decision not in ("for", "against", "abstain"):
        console.print("[red]✗[/red] Decision must be: for, against, or abstain")
        raise typer.Exit(1)
    
    api = ForgeAPI()
    
    # Get proposal details first
    with console.status("Fetching proposal..."):
        result = api.get_proposal(proposal_id)
    
    proposal = result["data"]
    
    console.print(Panel(
        f"[bold]{proposal['title']}[/bold]\n\n{proposal['description'][:200]}...",
        title="Proposal",
    ))
    
    if not Confirm.ask(f"Cast vote: [bold]{decision}[/bold]?"):
        console.print("Vote cancelled")
        return
    
    with console.status("Casting vote..."):
        api.cast_vote(proposal_id, decision=decision, reasoning=reason)
    
    console.print(f"[green]✓[/green] Vote cast: {decision}")
```

---

## 3. Web Dashboard

### 3.1 Project Structure

```
web/
├── package.json
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── capsules/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   ├── governance/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   └── settings/
│   │       └── page.tsx
│   ├── components/
│   │   ├── ui/              # Shadcn components
│   │   ├── capsules/
│   │   │   ├── CapsuleCard.tsx
│   │   │   ├── CapsuleList.tsx
│   │   │   ├── CreateCapsuleDialog.tsx
│   │   │   └── LineageViewer.tsx
│   │   ├── governance/
│   │   │   ├── ProposalCard.tsx
│   │   │   └── VotingPanel.tsx
│   │   └── layout/
│   │       ├── Sidebar.tsx
│   │       └── Header.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   └── utils.ts
│   └── hooks/
│       ├── useCapsules.ts
│       └── useGovernance.ts
└── tailwind.config.js
```

### 3.2 API Client

```typescript
// web/src/lib/api.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

class ForgeAPI {
  private accessToken: string | null = null;

  setToken(token: string) {
    this.accessToken = token;
  }

  private async fetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(this.accessToken && { Authorization: `Bearer ${this.accessToken}` }),
      ...options.headers,
    };

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || 'API request failed');
    }

    return response.json();
  }

  // Auth
  async login(email: string, password: string) {
    return this.fetch<{ access_token: string; refresh_token: string }>(
      '/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }
    );
  }

  // Capsules
  async listCapsules(params: { page?: number; type?: string } = {}) {
    const query = new URLSearchParams(params as any).toString();
    return this.fetch<{ data: Capsule[]; meta: PaginationMeta }>(
      `/capsules?${query}`
    );
  }

  async getCapsule(id: string) {
    return this.fetch<{ data: Capsule }>(`/capsules/${id}`);
  }

  async createCapsule(data: { content: string; type: string; parent_id?: string }) {
    return this.fetch<{ data: Capsule }>('/capsules', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async searchCapsules(query: string, limit = 10) {
    return this.fetch<{ data: SearchResult[] }>('/capsules/search', {
      method: 'POST',
      body: JSON.stringify({ query, limit }),
    });
  }

  async getLineage(id: string, maxDepth = 10) {
    return this.fetch<{ data: LineageResult }>(
      `/capsules/${id}/lineage?max_depth=${maxDepth}`
    );
  }

  // Governance
  async listProposals(params: { status?: string; page?: number } = {}) {
    const query = new URLSearchParams(params as any).toString();
    return this.fetch<{ data: Proposal[]; meta: PaginationMeta }>(
      `/governance/proposals?${query}`
    );
  }

  async castVote(proposalId: string, decision: string, reasoning?: string) {
    return this.fetch<{ data: Vote }>(
      `/governance/proposals/${proposalId}/vote`,
      {
        method: 'POST',
        body: JSON.stringify({ decision, reasoning }),
      }
    );
  }
}

export const api = new ForgeAPI();
```

### 3.3 Capsule Components

```tsx
// web/src/components/capsules/CapsuleCard.tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatDistanceToNow } from 'date-fns';

interface CapsuleCardProps {
  capsule: Capsule;
  onClick?: () => void;
}

export function CapsuleCard({ capsule, onClick }: CapsuleCardProps) {
  const typeColors: Record<string, string> = {
    knowledge: 'bg-blue-500',
    code: 'bg-green-500',
    decision: 'bg-purple-500',
    insight: 'bg-yellow-500',
  };

  return (
    <Card 
      className="cursor-pointer hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <Badge className={typeColors[capsule.type] || 'bg-gray-500'}>
            {capsule.type}
          </Badge>
          <Badge variant="outline">{capsule.trust_level}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-gray-600 line-clamp-3">
          {capsule.content}
        </p>
        <p className="text-xs text-gray-400 mt-2">
          {formatDistanceToNow(new Date(capsule.created_at), { addSuffix: true })}
        </p>
      </CardContent>
    </Card>
  );
}
```

```tsx
// web/src/components/capsules/LineageViewer.tsx
import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

interface LineageViewerProps {
  capsuleId: string;
  lineage: LineageEntry[];
}

export function LineageViewer({ capsuleId, lineage }: LineageViewerProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || lineage.length === 0) return;

    const width = 600;
    const height = 400;
    const nodeRadius = 30;

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    // Build tree data
    const nodes = [
      { id: capsuleId, depth: 0, label: 'Current' },
      ...lineage.map(e => ({
        id: e.capsule.id,
        depth: e.depth,
        label: e.capsule.type,
      })),
    ];

    // Position nodes vertically by depth
    const yScale = d3.scaleLinear()
      .domain([0, d3.max(nodes, d => d.depth) || 1])
      .range([50, height - 50]);

    // Draw links
    svg.selectAll('line')
      .data(lineage)
      .enter()
      .append('line')
      .attr('x1', width / 2)
      .attr('y1', d => yScale(d.depth - 1))
      .attr('x2', width / 2)
      .attr('y2', d => yScale(d.depth))
      .attr('stroke', '#ccc')
      .attr('stroke-width', 2);

    // Draw nodes
    const nodeGroups = svg.selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('transform', d => `translate(${width / 2}, ${yScale(d.depth)})`);

    nodeGroups.append('circle')
      .attr('r', nodeRadius)
      .attr('fill', d => d.depth === 0 ? '#3b82f6' : '#e5e7eb');

    nodeGroups.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 4)
      .attr('font-size', 10)
      .text(d => d.label);

  }, [capsuleId, lineage]);

  return (
    <div className="border rounded-lg p-4">
      <h3 className="font-semibold mb-2">Lineage (Isnad)</h3>
      <svg ref={svgRef} />
    </div>
  );
}
```

---

## 4. Mobile App (React Native)

### 4.1 Project Structure

```
mobile/
├── package.json
├── app.json
├── App.tsx
├── src/
│   ├── screens/
│   │   ├── LoginScreen.tsx
│   │   ├── DashboardScreen.tsx
│   │   ├── CapsuleListScreen.tsx
│   │   ├── CapsuleDetailScreen.tsx
│   │   ├── GovernanceScreen.tsx
│   │   └── VoteScreen.tsx
│   ├── components/
│   │   ├── CapsuleCard.tsx
│   │   ├── ProposalCard.tsx
│   │   └── QuickVote.tsx
│   ├── navigation/
│   │   └── AppNavigator.tsx
│   ├── services/
│   │   └── api.ts
│   └── hooks/
│       └── useAuth.ts
└── babel.config.js
```

### 4.2 Quick Vote Screen

```tsx
// mobile/src/screens/VoteScreen.tsx
import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Alert,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import { api } from '../services/api';

export function VoteScreen() {
  const route = useRoute();
  const navigation = useNavigation();
  const { proposal } = route.params as { proposal: Proposal };
  
  const [decision, setDecision] = useState<string | null>(null);
  const [reasoning, setReasoning] = useState('');
  const [loading, setLoading] = useState(false);

  const handleVote = async () => {
    if (!decision) {
      Alert.alert('Error', 'Please select a vote option');
      return;
    }

    setLoading(true);
    try {
      await api.castVote(proposal.id, decision, reasoning);
      Alert.alert('Success', 'Your vote has been recorded', [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (error) {
      Alert.alert('Error', 'Failed to submit vote');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{proposal.title}</Text>
      <Text style={styles.description}>{proposal.description}</Text>

      <View style={styles.voteButtons}>
        <TouchableOpacity
          style={[
            styles.voteButton,
            styles.forButton,
            decision === 'for' && styles.selected,
          ]}
          onPress={() => setDecision('for')}
        >
          <Text style={styles.buttonText}>For</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.voteButton,
            styles.againstButton,
            decision === 'against' && styles.selected,
          ]}
          onPress={() => setDecision('against')}
        >
          <Text style={styles.buttonText}>Against</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.voteButton,
            styles.abstainButton,
            decision === 'abstain' && styles.selected,
          ]}
          onPress={() => setDecision('abstain')}
        >
          <Text style={styles.buttonText}>Abstain</Text>
        </TouchableOpacity>
      </View>

      <TextInput
        style={styles.reasoningInput}
        placeholder="Optional: Add your reasoning..."
        value={reasoning}
        onChangeText={setReasoning}
        multiline
      />

      <TouchableOpacity
        style={[styles.submitButton, loading && styles.disabled]}
        onPress={handleVote}
        disabled={loading}
      >
        <Text style={styles.submitText}>
          {loading ? 'Submitting...' : 'Submit Vote'}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#fff' },
  title: { fontSize: 20, fontWeight: 'bold', marginBottom: 8 },
  description: { fontSize: 14, color: '#666', marginBottom: 24 },
  voteButtons: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16 },
  voteButton: { flex: 1, padding: 16, borderRadius: 8, marginHorizontal: 4, alignItems: 'center' },
  forButton: { backgroundColor: '#dcfce7' },
  againstButton: { backgroundColor: '#fee2e2' },
  abstainButton: { backgroundColor: '#f3f4f6' },
  selected: { borderWidth: 2, borderColor: '#3b82f6' },
  buttonText: { fontWeight: '600' },
  reasoningInput: { borderWidth: 1, borderColor: '#ddd', borderRadius: 8, padding: 12, height: 100, marginBottom: 16 },
  submitButton: { backgroundColor: '#3b82f6', padding: 16, borderRadius: 8, alignItems: 'center' },
  submitText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  disabled: { opacity: 0.5 },
});
```

---

## 5. Next Steps

After completing Phase 7, proceed to **Phase 8: DevOps & Deployment** to implement:

- Docker containerization
- Kubernetes manifests
- CI/CD pipelines
- Monitoring and observability
