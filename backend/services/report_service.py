"""
GEOAI-REP-01: PDF Executive Report Generator.
Uses ReportLab to create professional geospatial analysis reports.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch
import io
import datetime
import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt

def _find_best_metric(data: list, requested_metric: str) -> str:
    if not data:
        return requested_metric
    
    first_row = data[0]
    
    # Helper to check if a metric has any non-zero data in the set
    def is_active(m):
        try:
            return any(d.get(m, 0) != 0 for d in data)
        except:
            return False

    # If requested metric exists, is numeric, and has data, use it
    if requested_metric in first_row and isinstance(first_row[requested_metric], (int, float)) and is_active(requested_metric):
        return requested_metric
        
    # Otherwise, find the best numeric metric among all keys
    keys = first_row.keys()
    numeric_keys = [
        k for k in keys 
        if isinstance(first_row[k], (int, float)) and 
        not any(x in k.lower() for x in ['id', 'code', 'udise', 'sl_no', 'serial', 'index', 'pinc', 'pincode'])
    ]
    
    # Only consider keys that actually have non-zero data
    active_numeric_keys = [k for k in numeric_keys if is_active(k)]
    
    if not active_numeric_keys:
        return requested_metric
        
    # Score metrics to find the most relevant one
    def score_metric(k: str):
        k_lower = k.lower()
        if 'electricity' in k_lower or 'eletricity' in k_lower: return 100
        if 'water' in k_lower or 'computer' in k_lower: return 90
        if 'available' in k_lower or 'facility' in k_lower: return 80
        if 'density' in k_lower: return 75
        if 'coverage' in k_lower: return 70
        return 0
        
    active_numeric_keys.sort(key=score_metric, reverse=True)
    return active_numeric_keys[0]

def _generate_pie_chart(yes: int, no: int, issue: int, labels: list) -> io.BytesIO:
    """Generates a Pie Chart for overall status breakdown."""
    fig, ax = plt.subplots(figsize=(4, 3))
    data = []
    plot_labels = []
    colors_list = []
    
    if yes > 0: data.append(yes); plot_labels.append(labels[0]); colors_list.append('#10b981')
    if issue > 0: data.append(issue); plot_labels.append(labels[2]); colors_list.append('#f59e0b')
    if no > 0: data.append(no); plot_labels.append(labels[1]); colors_list.append('#ef4444')
    
    if not data: return None
    
    ax.pie(data, labels=plot_labels, autopct='%1.1f%%', startangle=140, colors=colors_list, textprops={'fontsize': 8})
    ax.set_title("Overall Compliance Breakdown", fontsize=10, pad=10)
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer

def _generate_bar_chart(dist_data: dict) -> io.BytesIO:
    """Generates a Bar Chart for Top 10 impacted districts."""
    if not dist_data: return None
    
    # Sort and take top 10 by missing count
    sorted_dists = sorted(dist_data.items(), key=lambda x: x[1]['missing'], reverse=True)[:10]
    names = [d[0] for d in sorted_dists]
    counts = [d[1]['missing'] for d in sorted_dists]
    
    fig, ax = plt.subplots(figsize=(6, 3))
    bars = ax.bar(names, counts, color='#3b82f6')
    ax.set_title("Top 10 Districts by Missing Infrastructure", fontsize=10, pad=10)
    ax.set_ylabel("Number of Schools", fontsize=8)
    plt.xticks(rotation=45, ha='right', fontsize=7)
    plt.yticks(fontsize=7)
    
    # Add labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{int(height)}', ha='center', va='bottom', fontsize=7)
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer

def generate_pdf_report(metric: str, data: list, summary: str = None) -> io.BytesIO:
    """
    Generates a PDF report for the current data selection.
    """
    # Auto-detect better metric if current one is generic or missing
    resolved_metric = _find_best_metric(data, metric)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor("#1e3a8a"),
        spaceAfter=30,
        alignment=1 # Center
    )
    
    header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor("#334155"),
        spaceBefore=12,
        spaceAfter=12,
        underline=True
    )

    elements = []

    # 1. Title Page
    elements.append(Paragraph("Meghalaya GeoAI Intelligence Report", title_style))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Paragraph(f"Analysis Metric: {resolved_metric.replace('_', ' ').upper()}", styles['Normal']))
    elements.append(Spacer(1, 0.5 * inch))

    # 2. Executive Summary (AI Insights)
    if summary:
        # Determine if we have a structured object or a plain string
        analysis_points = []
        policy_points = []

        if isinstance(summary, dict):
            # Extract points from structured object
            s_raw = summary.get('summary', [])
            r_raw = summary.get('recommendations', [])
            analysis_points = s_raw if isinstance(s_raw, list) else [str(s_raw)]
            policy_points = r_raw if isinstance(r_raw, list) else [str(r_raw)]
        else:
            # Legacy string support
            analysis_points = [str(summary)]

        # Render Analytical Report
        if analysis_points:
            elements.append(Paragraph("Analytical Report", header_style))
            for pt in analysis_points:
                clean_pt = pt.replace('###', '').replace('##', '').replace('**', '').replace('*', '').strip()
                elements.append(Paragraph(f"• {clean_pt}", styles['Normal']))
            elements.append(Spacer(1, 0.2 * inch))

        # Render Policy Recommendations
        if policy_points:
            elements.append(Paragraph("Strategic Policy Recommendations", header_style))
            for pt in policy_points:
                clean_pt = pt.replace('###', '').replace('##', '').replace('**', '').replace('*', '').strip()
                elements.append(Paragraph(f"• {clean_pt}", styles['Normal']))
            elements.append(Spacer(1, 0.3 * inch))

    # Detect all relevant infrastructure columns in the current dataset
    infra_keywords = ['solar', 'panel', 'electricity', 'eletricity', 'water', 'toilet', 'computer', 'facility', 'internet', 'smart', 'ramp', 'playground', 'lab', 'library', 'boundary', 'quarters', 'furniture', 'books', 'extinguisher', 'uniform', 'textbook', 'hostel', 'room', 'handwash', 'equipment', 'laboratory', 'board', 'projector', 'tablet', 'desktop', 'laptop', 'sanitary']
    raw_detected_infra = [k for k in data[0].keys() if any(ik in k.lower() for ik in infra_keywords) and k not in ['id', 'udise_code', 'udise_num']] if data else []
    
    # Filter based on the query 'metric' to prevent intersection across unrequested LLM-returned columns
    detected_infra = []
    if metric:
        q_lower = metric.lower()
        for k in raw_detected_infra:
            k_lower = k.lower()
            for ik in infra_keywords:
                if ik in k_lower:
                    if ik in q_lower or (ik == 'eletricity' and 'electricity' in q_lower) or (ik == 'electricity' and 'eletricity' in q_lower):
                        if k not in detected_infra:
                            detected_infra.append(k)
                    elif ik == 'facility' or ik == 'panel':
                        if ('internet' in k_lower and 'internet' in q_lower) or ('medical' in k_lower and 'medical' in q_lower) or ('library' in k_lower and 'library' in q_lower):
                            if k not in detected_infra:
                                detected_infra.append(k)
    
    if not detected_infra:
        detected_infra = raw_detected_infra
    # Detect query type
    is_multi = len(detected_infra) > 1
    # Check if the resolved metric is a binary one (usually 1/0 or yes/no)
    is_binary = any(d.get(resolved_metric) in [1, 1.0, 0, 0.0, 'yes', 'no', 'Yes', 'No'] for d in data[:5]) if data else False
    
    if (is_multi or is_binary) and data:
        elements.append(Paragraph("Executive Metrics Summary", header_style))
        
        # Robust counting (numeric 1/0/2 OR string 'Yes'/'No')
        def check_val(d, target):
            # Standardized definition matching Dashboard and AI Summary
            positives = ['1', '1.0', 'yes', 'true', 'functional', 'satisfactory', 'available', 'provided']
            negatives = ['0', '0.0', 'no', 'false', 'none', 'unavailable', 'missing']
            
            # If we're checking multi, we iterate; if single, we use resolved_metric
            metrics_to_check = detected_infra if is_multi else [resolved_metric]
            
            def match(val, t):
                v_str = str(val).lower().strip()
                if t == 'yes': return val == 1 or val == 1.0 or v_str in positives
                if t == 'no': return val == 0 or val == 0.0 or v_str in negatives
                if t == 'issue': return val == 2 or any(x in v_str for x in ['issue', 'partial', 'repair', 'not functional'])
                return False

            if target == 'yes':
                return all(match(d.get(m), 'yes') for m in metrics_to_check)
            if target == 'no':
                return all(match(d.get(m), 'no') for m in metrics_to_check)
            if target == 'issue':
                if is_multi:
                    # For multi, an 'issue' is any partial compliance
                    has_any_yes = any(match(d.get(m), 'yes') for m in metrics_to_check)
                    is_all_yes = all(match(d.get(m), 'yes') for m in metrics_to_check)
                    return has_any_yes and not is_all_yes
                return match(d.get(resolved_metric), 'issue')
            return False

        yes_count = len([d for d in data if check_val(d, 'yes')])
        no_count = len([d for d in data if check_val(d, 'no')])
        issue_count = len([d for d in data if check_val(d, 'issue')])
        total = len(data)
        
        if is_multi:
            label = f"All {len(detected_infra)} Met"
            neg_label = "None"
            issue_label = "Partial"
        else:
            label = "Yes/Available"
            neg_label = "No/Unavailable"
            issue_label = "Functional Issue"
        
        summary_text = f"<b>Total Records:</b> {total}<br/>" \
                       f"<b>{label}:</b> {yes_count} ({round(yes_count/total*100, 1) if total > 0 else 0}%)<br/>" \
                       f"<b>{neg_label}:</b> {no_count} ({round(no_count/total*100, 1) if total > 0 else 0}%)<br/>"
        
        if is_multi or issue_count > 0:
            summary_text += f"<b>{issue_label}:</b> {issue_count} ({round(issue_count/total*100, 1) if total > 0 else 0}%)"
            
        elements.append(Paragraph(summary_text, styles['Normal']))
        
        # --- GENERATE AND ADD PIE CHART ---
        labels = [label, neg_label, issue_label]
        pie_buf = _generate_pie_chart(yes_count, no_count, issue_count, labels)
        if pie_buf:
            elements.append(Image(pie_buf, width=3.5*inch, height=2.6*inch))
            elements.append(Spacer(1, 0.3 * inch))
        else:
            elements.append(Spacer(1, 0.3 * inch))

        # 2a. District Summary Table
        elements.append(Paragraph("District-Level Performance Summary", header_style))
        dist_data = {}
        for d in data:
            dist = d.get('district_name') or d.get('DISTRICT') or "Unknown"
            if dist not in dist_data: dist_data[dist] = {'total': 0, 'missing': 0}
            dist_data[dist]['total'] += 1
            if check_val(d, 'no'): dist_data[dist]['missing'] += 1
        
        dist_table_data = [["District", "Total Schools", "Missing Gaps", "% Impacted"]]
        for dist, stats in sorted(dist_data.items(), key=lambda x: x[1]['missing'], reverse=True)[:10]:
            dist_table_data.append([
                dist, 
                str(stats['total']), 
                str(stats['missing']), 
                f"{round(stats['missing']/stats['total']*100, 1)}%" if stats['total'] > 0 else "0%"
            ])
        
        dt = Table(dist_table_data, colWidths=[2.5 * inch, 1.2 * inch, 1.2 * inch, 1.1 * inch])
        dt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ]))
        elements.append(dt)
        
        # --- GENERATE AND ADD BAR CHART ---
        bar_buf = _generate_bar_chart(dist_data)
        if bar_buf:
            elements.append(Spacer(1, 0.2 * inch))
            elements.append(Image(bar_buf, width=5.5*inch, height=2.7*inch))
            elements.append(Spacer(1, 0.3 * inch))
        else:
            elements.append(Spacer(1, 0.3 * inch))

        # 2b. Block Summary Table
        elements.append(Paragraph("Top 10 High-Impact Blocks", header_style))
        block_data = {}
        for d in data:
            block = d.get('block_name') or d.get('BLOCK') or "Unknown"
            if block not in block_data: block_data[block] = {'total': 0, 'missing': 0, 'dist': d.get('district_name') or "-"}
            block_data[block]['total'] += 1
            if check_val(d, 'no'): block_data[block]['missing'] += 1
        
        block_table_data = [["Block", "Parent District", "Missing", "% Impact"]]
        for block, stats in sorted(block_data.items(), key=lambda x: x[1]['missing'], reverse=True)[:10]:
            block_table_data.append([
                block, 
                stats['dist'], 
                str(stats['missing']), 
                f"{round(stats['missing']/stats['total']*100, 1)}%" if stats['total'] > 0 else "0%"
            ])
        
        bt = Table(block_table_data, colWidths=[2.0 * inch, 1.7 * inch, 1.1 * inch, 1.2 * inch])
        bt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f0f9ff")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#0369a1")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ]))
        elements.append(bt)
        elements.append(Spacer(1, 0.3 * inch))

    # 3. Data Overview Table
    elements.append(Paragraph("Regional Metric Breakdown", header_style))
    
    # Prepare table data
    table_data = [["School/Location", "Block", "District", "Value", "Rank"]]
    
    # Sort data by value descending (if numeric)
    def sort_func(x):
        v = x.get(resolved_metric, 0)
        try: return float(v)
        except: return 0.0

    display_data = sorted(data, key=sort_func, reverse=True)[:100]
    
    for item in display_data:
        name = item.get('schoolName') or item.get('display_name') or item.get('schname') or "N/A"
        block = item.get('block_name') or item.get('BLOCK') or "-"
        district = item.get('district_name') or item.get('DISTRICT') or "-"
        val = item.get(resolved_metric, 0)
        rank = item.get('priority_rank') or item.get('rank') or "-"
        
        table_data.append([
            Paragraph(name, styles['Normal']),
            Paragraph(block, styles['Normal']),
            Paragraph(district, styles['Normal']),
            str(round(val, 2)) if isinstance(val, (int, float)) else str(val),
            str(rank)
        ])

    t = Table(table_data, colWidths=[2.2 * inch, 1.2 * inch, 1.2 * inch, 0.8 * inch, 0.6 * inch], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#64748b")),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
    ]))
    elements.append(t)
    
    # 4. Footer
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph("* This is an AI-generated report for policy making support. Please verify critical spatial data points.", 
                            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)))

    doc.build(elements)
    buffer.seek(0)
    return buffer
