# utils/app_charts.py 
import plotly.graph_objects as go
from utils import app_utils as U

def create_revenue_benchmark_chart(dealer):
    dealer_90d_average_monthly = U.safe_get(dealer, 'total_revenue_last_90d', 0) / 3.0
    dealer_180d_average_monthly = U.safe_get(dealer, 'avg_monthly_revenue_180d', 0)
    dealer_lifetime_average_monthly = U.safe_get(dealer, 'avg_monthly_revenue_lifetime', 0.0)

    cluster_monthly = U.safe_get(dealer, 'cluster_avg_monthly_revenue_last_90d', 0)
    cluster_monthly_180d = U.safe_get(dealer, 'cluster_avg_monthly_revenue_180d', 0)
    cluster_monthly_lifetime = U.safe_get(dealer, 'cluster_avg_monthly_revenue_lifetime', 0)

    terr_monthly = U.safe_get(dealer, 'territory_avg_monthly_revenue_last_90d', 0)
    terr_monthly_180d = U.safe_get(dealer, 'territory_avg_monthly_revenue_180d', 0)
    terr_monthly_lifetime = U.safe_get(dealer, 'territory_avg_monthly_revenue_lifetime', 0)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='This Dealer',
        x=['3-Mo Avg', '6-Mo Avg', 'Lifetime Avg'],
        y=[dealer_90d_average_monthly, dealer_180d_average_monthly, dealer_lifetime_average_monthly],
        marker_color='#667eea',
        text=[U.fmt_rs(dealer_90d_average_monthly), U.fmt_rs(dealer_180d_average_monthly), U.fmt_rs(dealer_lifetime_average_monthly)],
        textposition='outside',
        textfont_size=10
    ))

    fig.add_trace(go.Scatter(
        name='Cluster Avg',
        x=['3-Mo Avg', '6-Mo Avg', 'Lifetime Avg'],
        y=[cluster_monthly, cluster_monthly_180d, cluster_monthly_lifetime],
        mode='lines+markers',
        line=dict(width=3, dash='dash', color='#48bb78'),
        marker=dict(size=8, color='#48bb78')
    ))

    fig.add_trace(go.Scatter(
        name='Territory Avg',
        x=['3-Mo Avg', '6-Mo Avg', 'Lifetime Avg'],
        y=[terr_monthly, terr_monthly_180d, terr_monthly_lifetime],
        mode='lines+markers',
        line=dict(width=3, dash='dot', color='#ed8936'),
        marker=dict(size=8, color='#ed8936')
    ))

    fig.update_layout(
        title='Monthly Revenue Benchmarking vs Peers',
        height=400,
        showlegend=True,
        template='plotly_white',
        yaxis_title='Avg Monthly Revenue (₹)',
        margin=dict(t=60, b=60, l=60, r=20)
    )
    return fig

def create_order_frequency_benchmark(dealer):
    dealer_orders = U.safe_get(dealer, 'total_orders_last_90d', 0)
    cluster_avg = U.safe_get(dealer, 'cluster_avg_orders_last_90d', 0)
    terr_avg = U.safe_get(dealer, 'territory_avg_orders_last_90d', 0)
    terr_p80 = U.safe_get(dealer, 'territory_p80_orders_last_90d', 0)

    fig = go.Figure(data=[
        go.Bar(
            x=['This Dealer', 'Cluster Avg', 'Territory Avg', 'Territory Top 20%'],
            y=[dealer_orders, cluster_avg, terr_avg, terr_p80],
            marker_color=['#667eea', '#48bb78', '#48bb78', '#48bb78'],
            text=[int(dealer_orders), f'{cluster_avg:.0f}', f'{terr_avg:.0f}', f'{terr_p80:.0f}'],
            textposition='outside',
            textfont_size=11
        )
    ])
    fig.update_layout(
        title='Order Frequency Comparison (Last 90 Days)',
        height=400,
        template='plotly_white',
        yaxis_title='Number of Orders',
        showlegend=False,
        margin=dict(t=60, b=60, l=60, r=20)
    )
    return fig

def create_subbrand_mix_chart(dealer):
    subbrands = {
        "Allwood": U.safe_get(dealer, "share_revenue_allwood_180d", 0.0),
        "Prime": U.safe_get(dealer, "share_revenue_prime_180d", 0.0),
        "Allwood Pro": U.safe_get(dealer, "share_revenue_allwoodpro_180d", 0.0),
        "One": U.safe_get(dealer, "share_revenue_one_180d", 0.0),
        "Calista": U.safe_get(dealer, "share_revenue_calista_180d", 0.0),
        "Style": U.safe_get(dealer, "share_revenue_style_180d", 0.0),
        "AllDry": U.safe_get(dealer, "share_revenue_alldry_180d", 0.0),
        "Artist": U.safe_get(dealer, "share_revenue_artist_180d", 0.0),
        "Sample Kit": U.safe_get(dealer, "share_revenue_samplekit_180d", 0.0),
        "Collaterals": U.safe_get(dealer, "share_revenue_collaterals_180d", 0.0),
    }
    subbrands = {k: v for k, v in subbrands.items() if v and v > 0}
    if not subbrands:
        return None

    fig = go.Figure(data=[go.Pie(
        labels=list(subbrands.keys()),
        values=list(subbrands.values()),
        hole=0.4,
        textinfo="label+percent",
        textposition="inside",
        textfont_size=11,
    )])

    fig.update_layout(
        title="Sub-brand Revenue Mix (Last 6 Months)",
        height=400,
        template="plotly_white",
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02),
        margin=dict(t=60, b=20, l=20, r=120),
    )
    return fig
