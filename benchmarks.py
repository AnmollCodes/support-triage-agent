"""
Performance benchmarking suite for Support Triage Agent
Run with: python benchmarks.py
"""
import time
import sys
import os
import csv
import statistics
from typing import Dict, List, Any, Optional, TYPE_CHECKING

# Add code directory to path
code_dir = os.path.join(os.path.dirname(__file__), 'code')
sys.path.insert(0, code_dir)

if TYPE_CHECKING:
    from agent import SupportTriageAgent

from agent import SupportTriageAgent

class Benchmarks:
    def __init__(self) -> None:
        self.agent: SupportTriageAgent = SupportTriageAgent()
        self.results: Dict[str, Any] = {}
    
    def benchmark_single_ticket(self, iterations: int = 10) -> None:
        """Benchmark single ticket processing"""
        print("📊 Benchmarking single ticket processing...")
        
        ticket: Dict[str, str] = {
            'issue': 'I lost access to my account and cannot login',
            'subject': 'Account access lost',
            'company': 'Claude'
        }
        
        times: List[float] = []
        for i in range(iterations):
            start: float = time.time()
            self.agent.process(ticket)
            elapsed: float = time.time() - start
            times.append(elapsed)
            print(f"  Iteration {i+1}/{iterations}: {elapsed*1000:.2f}ms")
        
        self.results['single_ticket'] = {
            'min': min(times),
            'max': max(times),
            'mean': statistics.mean(times),
            'median': statistics.median(times),
            'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        }
    
    def benchmark_batch_processing(self, batch_sizes: Optional[List[int]] = None) -> None:
        """Benchmark batch processing"""
        if batch_sizes is None:
            batch_sizes = [10, 50, 100]
        print("\n📊 Benchmarking batch processing...")
        
        base_ticket: Dict[str, str] = {
            'issue': 'I cannot access my account',
            'subject': 'Access issue',
            'company': 'Claude'
        }
        
        for batch_size in batch_sizes:
            tickets: List[Dict[str, str]] = [base_ticket.copy() for _ in range(batch_size)]
            
            start: float = time.time()
            results: List[Any] = []
            for ticket in tickets:
                result: Any = self.agent.process(ticket)
                results.append(result)
            elapsed: float = time.time() - start
            
            avg_per_ticket: float = elapsed / batch_size
            throughput: float = batch_size / elapsed
            
            print(f"  Batch size {batch_size}: {elapsed:.2f}s ({throughput:.1f} tickets/sec, {avg_per_ticket*1000:.2f}ms per ticket)")
            
            self.results[f'batch_{batch_size}'] = {
                'total_time': elapsed,
                'avg_per_ticket': avg_per_ticket,
                'throughput': throughput,
            }
    
    def benchmark_different_companies(self) -> None:
        """Benchmark processing for different companies"""
        print("\n📊 Benchmarking different company domains...")
        
        tickets: Dict[str, Dict[str, str]] = {
            'Claude': {
                'issue': 'I lost access to my workspace',
                'subject': 'Claude workspace access',
                'company': 'Claude'
            },
            'HackerRank': {
                'issue': 'My test results are not showing',
                'subject': 'HackerRank test results',
                'company': 'HackerRank'
            },
            'Visa': {
                'issue': 'My card was charged twice',
                'subject': 'Duplicate charge',
                'company': 'Visa'
            }
        }
        
        for company, ticket in tickets.items():
            times: List[float] = []
            for _ in range(5):
                start: float = time.time()
                self.agent.process(ticket)
                elapsed: float = time.time() - start
                times.append(elapsed)
            
            avg_time: float = statistics.mean(times)
            print(f"  {company}: {avg_time*1000:.2f}ms average")
            
            self.results[f'company_{company}'] = {
                'avg_time': avg_time,
                'min_time': min(times),
                'max_time': max(times),
            }
    
    def benchmark_memory_usage(self) -> None:
        """Benchmark memory consumption"""
        print("\n📊 Benchmarking memory usage...")
        
        import tracemalloc
        
        # Warm up
        ticket: Dict[str, str] = {
            'issue': 'Test',
            'subject': 'Test',
            'company': 'Claude'
        }
        self.agent.process(ticket)
        
        # Measure
        tracemalloc.start()
        
        for _ in range(10):
            self.agent.process(ticket)
        
        current: int
        peak: int
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        print(f"  Current memory: {current / 1024 / 1024:.2f} MB")
        print(f"  Peak memory: {peak / 1024 / 1024:.2f} MB")
        
        self.results['memory'] = {
            'current': current,
            'peak': peak,
        }
    
    def print_summary(self) -> None:
        """Print summary of all benchmarks"""
        print("\n" + "="*60)
        print("📈 BENCHMARK SUMMARY")
        print("="*60 + "\n")
        
        # Single ticket
        if 'single_ticket' in self.results:
            st: Dict[str, Any] = self.results['single_ticket']
            print("⏱️  Single Ticket Processing:")
            print(f"   Mean: {st['mean']*1000:.2f}ms")
            print(f"   Min: {st['min']*1000:.2f}ms")
            print(f"   Max: {st['max']*1000:.2f}ms")
            print(f"   Stdev: {st['stdev']*1000:.2f}ms\n")
        
        # Batch processing
        print("📦 Batch Processing:")
        for key, val in self.results.items():
            if key.startswith('batch_'):
                batch_size: str = key.split('_')[1]
                print(f"   Batch {batch_size}: {val['throughput']:.1f} tickets/sec")
        print()
        
        # Different companies
        print("🏢 By Company:")
        for key, val in self.results.items():
            if key.startswith('company_'):
                company: str = key.split('company_')[1]
                print(f"   {company}: {val['avg_time']*1000:.2f}ms avg")
        print()
        
        # Memory
        if 'memory' in self.results:
            mem: Dict[str, int] = self.results['memory']
            print("💾 Memory Usage:")
            print(f"   Current: {mem['current'] / 1024 / 1024:.2f} MB")
            print(f"   Peak: {mem['peak'] / 1024 / 1024:.2f} MB\n")
    
    def save_results(self, filename: str = 'benchmarks_results.csv') -> None:
        """Save results to CSV"""
        print(f"\n✓ Saving results to {filename}...")
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Benchmark', 'Metric', 'Value'])
            
            for benchmark_name, metrics in self.results.items():
                for metric_name, metric_value in metrics.items():
                    writer.writerow([benchmark_name, metric_name, metric_value])
        
        print(f"✓ Results saved")

def run_full_benchmark() -> None:
    """Run complete benchmark suite"""
    print("🚀 Support Triage Agent - Performance Benchmark Suite")
    print("="*60 + "\n")
    
    bench: Benchmarks = Benchmarks()
    
    # Run benchmarks
    bench.benchmark_single_ticket(iterations=5)
    bench.benchmark_batch_processing(batch_sizes=[10, 50, 100])
    bench.benchmark_different_companies()
    bench.benchmark_memory_usage()
    
    # Print and save results
    bench.print_summary()
    bench.save_results()

if __name__ == '__main__':
    try:
        run_full_benchmark()
    except KeyboardInterrupt:
        print("\n\n❌ Benchmark interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
