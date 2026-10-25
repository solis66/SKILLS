#!/usr/bin/env python3
import json, sys, os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.colors import HexColor, grey
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))

WIN_FONT = 'C:/Windows/Fonts'
FONT_MAP = {
    'simsun': ('simsun.ttc', 'SimSun'),
    'simhei': ('simhei.ttf', 'SimHei'),
    'simkai': ('simkai.ttf', 'KaiTi'),
    'fangsong': ('simfang.ttf', 'FangSong'),
}
for key, (fname, fdisplay) in FONT_MAP.items():
    fp = os.path.join(WIN_FONT, fname)
    if os.path.exists(fp):
        try:
            pdfmetrics.registerFont(TTFont(fdisplay, fp))
        except Exception:
            pass

def safe_font(name):
    for f in [name, 'STSong-Light', 'SimSun', 'HeiseiKakuGo-W5', 'Helvetica']:
        try:
            pdfmetrics.getFont(f)
            return f
        except Exception:
            continue
    return 'Helvetica'

FONT_SONG = safe_font('SimSun')
FONT_HEI = safe_font('SimHei')
FONT_KAI = safe_font('KaiTi')
FONT_FANG = safe_font('FangSong')

PAGE_W, PAGE_H = A4
TOP_M = 3.7 * cm
BOT_M = 3.5 * cm
LEFT_M = 2.8 * cm
RIGHT_M = 2.8 * cm

SZ_TITLE = 22
SZ_H1 = 16
SZ_H2 = 14
SZ_BODY = 12
SZ_SM = 9

style_h1 = ParagraphStyle('H1', fontName=FONT_HEI, fontSize=SZ_H1,
    leading=SZ_H1*1.8, alignment=TA_LEFT, spaceBefore=16, spaceAfter=8)
style_h2 = ParagraphStyle('H2', fontName=FONT_HEI, fontSize=SZ_H2,
    leading=SZ_H2*1.6, alignment=TA_LEFT, spaceBefore=12, spaceAfter=6)
style_body = ParagraphStyle('Body', fontName=FONT_SONG, fontSize=SZ_BODY,
    leading=SZ_BODY*2.1, firstLineIndent=SZ_BODY*2,
    spaceBefore=0, spaceAfter=4, alignment=TA_JUSTIFY)
style_body_ni = ParagraphStyle('BodyNI', fontName=FONT_SONG, fontSize=SZ_BODY,
    leading=SZ_BODY*2.1, spaceBefore=0, spaceAfter=4, alignment=TA_JUSTIFY)
style_bullet = ParagraphStyle('Bullet', fontName=FONT_SONG, fontSize=SZ_BODY,
    leading=SZ_BODY*1.5, leftIndent=SZ_BODY*1.5,
    spaceBefore=0, spaceAfter=3, alignment=TA_LEFT)
style_cover_t = ParagraphStyle('CT', fontName=FONT_HEI, fontSize=26,
    leading=38, alignment=TA_CENTER, spaceBefore=0, spaceAfter=20)
style_cover_s = ParagraphStyle('CS', fontName=FONT_SONG, fontSize=SZ_H1,
    leading=28, alignment=TA_CENTER, spaceBefore=0, spaceAfter=10)
style_sm = ParagraphStyle('Sm', fontName=FONT_KAI, fontSize=SZ_SM,
    leading=SZ_SM*1.5, spaceBefore=0, spaceAfter=2)
style_cell = ParagraphStyle('Cell', fontName=FONT_SONG, fontSize=SZ_SM+1,
    leading=(SZ_SM+1)*1.5, alignment=TA_CENTER)
style_cell_h = ParagraphStyle('CellH', fontName=FONT_HEI, fontSize=SZ_SM+1,
    leading=(SZ_SM+1)*1.5, alignment=TA_CENTER)
style_ref = ParagraphStyle('Ref', fontName=FONT_SONG, fontSize=SZ_SM+1,
    leading=(SZ_SM+1)*1.8, spaceBefore=0, spaceAfter=2,
    leftIndent=SZ_BODY*2)

from reportlab.pdfgen import canvas as rl_canvas

class NumCanvas(rl_canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def showPage(self):
        if self.getPageNumber() >= 1:
            self.saveState()
            self.setFont('Times-Roman', SZ_SM)
            self.drawCentredString(PAGE_W/2, 2.0*cm, str(self.getPageNumber() + 1))
            self.restoreState()
        super().showPage()

def load(path):
    return json.load(open(path, 'r', encoding='utf-8-sig'))

def make_table(headers, rows, col_widths=None):
    hcells = [Paragraph(h, style_cell_h) for h in headers]
    data = [hcells]
    for row in rows:
        data.append([Paragraph(str(c), style_cell) for c in row])
    if col_widths is None:
        avail = PAGE_W - LEFT_M - RIGHT_M
        col_widths = [avail/len(headers)] * len(headers)
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#2B579A')),
        ('TEXTCOLOR', (0,0), (-1,0), HexColor('#FFFFFF')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, grey),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#F2F2F2'), HexColor('#FFFFFF')]),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    return t

def generate(input_path, output_path):
    d = load(input_path)
    # 自动在输出路径中插入日期目录：output/{MM-DD}/文件名
    gen_date = d.get('gen_date', '')
    output_path = Path(output_path)
    if gen_date:
        try:
            mm_dd = gen_date.split('-')[1] + '-' + gen_date.split('-')[2]
        except IndexError:
            mm_dd = ''
        # 仅当路径中尚未包含日期目录时才插入
        if mm_dd and mm_dd not in str(output_path):
            output_path = output_path.parent / mm_dd / output_path.name
    output_path = str(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=A4,
        topMargin=TOP_M, bottomMargin=BOT_M,
        leftMargin=LEFT_M, rightMargin=RIGHT_M,
        title=d.get('company','')+d.get('position','')+'岗位调研报告',
        author='岗位调研报告生成器')
    story = []

    # cover
    story.append(Spacer(1, 4*cm))
    story.append(Paragraph('岗位调研报告', style_cover_t))
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph(d.get('company','') + ' \u00b7 ' + d.get('position',''), style_cover_s))
    story.append(Spacer(1, 0.8*cm))
    rd = d.get('report_date','')
    gd = d.get('gen_date','')
    if rd:
        story.append(Paragraph('调研日期：' + rd, style_sm))
    if gd:
        story.append(Paragraph('报告生成日期：' + gd, style_sm))
    story.append(PageBreak())

    # section 1 - company
    ci = d.get('company_info', {})
    story.append(Paragraph('一、公司概况', style_h1))
    story.append(Paragraph('（一）行业定位', style_h2))
    for line in ci.get('industry', []):
        story.append(Paragraph(line, style_body))
    story.append(Paragraph('（二）公司规模', style_h2))
    for line in ci.get('scale', []):
        story.append(Paragraph(line, style_body))
    dev_stage = ci.get('development_stage', [])
    if dev_stage:
        story.append(Paragraph('（三）发展阶段', style_h2))
        for line in dev_stage:
            story.append(Paragraph(line, style_body))
    story.append(Paragraph('（四）企业文化', style_h2))
    for line in ci.get('culture', []):
        story.append(Paragraph(line, style_body))

    # section 2 - JD
    jd = d.get('job_description', {})
    story.append(Paragraph('二、岗位职责', style_h1))
    ov = jd.get('overview','')
    if ov:
        story.append(Paragraph(ov, style_body))
    duties = jd.get('duties', [])
    if duties:
        story.append(Paragraph('具体职责包括：', style_body))
        for i, duty in enumerate(duties, 1):
            story.append(Paragraph(str(i)+'. '+duty, style_bullet))
    reqs = jd.get('requirements', [])
    if reqs:
        story.append(Paragraph('任职要求：', style_body))
        for r in reqs:
            story.append(Paragraph('\u00b7 '+r, style_bullet))

    # section 3 - salary
    sal = d.get('salary', {})
    story.append(Paragraph('三、薪资范围', style_h1))
    bc = sal.get('by_city', [])
    if bc:
        story.append(Paragraph('（一）按城市划分', style_h2))
        story.append(Paragraph('以下为不同城市该岗位的薪资区间参考：', style_body))
        story.append(Spacer(1, 4))
        story.append(make_table(['城市','薪资范围（月薪）','备注'],
            [[c.get('city',''),c.get('range',''),c.get('note','')] for c in bc]))
        story.append(Spacer(1, 6))
    be = sal.get('by_experience', [])
    if be:
        story.append(Paragraph('（二）按经验划分', style_h2))
        story.append(Spacer(1, 4))
        story.append(make_table(['经验年限','薪资范围（月薪）','备注'],
            [[e.get('level',''),e.get('range',''),e.get('note','')] for e in be]))
        story.append(Spacer(1, 6))
    br = sal.get('by_rank', [])
    if br:
        story.append(Paragraph('（三）按职级划分', style_h2))
        story.append(Spacer(1, 4))
        story.append(make_table(['职级','薪资范围（月薪）','备注'],
            [[r.get('rank',''),r.get('range',''),r.get('note','')] for r in br]))
        story.append(Spacer(1, 6))

    # section 4 - skills
    sk = d.get('skills', {})
    story.append(Paragraph('四、技能要求', style_h1))
    story.append(Paragraph('（一）硬技能', style_h2))
    for item in sk.get('hard_skills', []):
        story.append(Paragraph('\u00b7 '+item, style_bullet))
    story.append(Paragraph('（二）软技能', style_h2))
    for item in sk.get('soft_skills', []):
        story.append(Paragraph('\u00b7 '+item, style_bullet))

    # references
    refs = d.get('references', [])
    if refs:
        story.append(PageBreak())
        story.append(Paragraph('参考文献', style_h1))
        for ref in refs:
            story.append(Paragraph(ref, style_ref))

    doc.build(story, canvasmaker=NumCanvas)

    if os.path.exists(output_path):
        sz = os.path.getsize(output_path)/1024
        print(f'[OK] PDF generated: {output_path} ({sz:.1f} KB)')
    else:
        print('[ERROR] PDF generation failed')
        sys.exit(1)

def print_sample():
    sample = {
        'company': '示例科技有限公司',
        'position': '产品经理',
        'report_date': '2026年6月',
        'gen_date': '2026-06-18',
        'company_info': {
            'industry': [
                '示例科技是一家专注于人工智能领域的互联网公司，主营业务涵盖大语言模型、智能助手等产品方向。',
                '所属行业：人工智能 / 互联网科技，赛道热度持续走高。'
            ],
            'scale': [
                '公司成立于2020年，总部位于北京，在上海、深圳设有分公司。目前员工规模约3000人。',
                '公司已完成D轮融资，估值超过50亿美元，处于快速扩张阶段。'
            ],
            'culture': [
                '公司倡导技术驱动、用户至上的价值观，扁平化管理，鼓励内部创新。',
                '工作时间弹性，提供完善的培训体系和晋升通道。'
            ]
        },
        'job_description': {
            'overview': '产品经理负责产品的整体规划、需求分析、功能设计及迭代优化，是连接技术、设计与业务的核心角色。',
            'duties': [
                '负责产品需求调研与分析，输出高质量PRD文档',
                '协调研发、设计、测试团队推动产品迭代',
                '跟踪产品数据，制定优化策略',
                '参与产品战略规划与竞品分析'
            ],
            'requirements': [
                '本科及以上学历，计算机或相关专业优先',
                '3年以上互联网产品经验',
                '具备数据分析能力，熟练使用SQL',
                '优秀的沟通协调能力与逻辑思维'
            ]
        },
        'salary': {
            'by_city': [
                {'city':'北京','range':'25K-45K','note':'一线城市，大厂偏高'},
                {'city':'上海','range':'22K-40K','note':''},
                {'city':'杭州','range':'20K-38K','note':''}
            ],
            'by_experience': [
                {'level':'1-3年','range':'15K-25K','note':'初级'},
                {'level':'3-5年','range':'25K-40K','note':'中级'},
                {'level':'5-10年','range':'40K-70K','note':'高级/总监'}
            ],
            'by_rank': [
                {'rank':'产品专员','range':'10K-18K','note':''},
                {'rank':'产品经理','range':'20K-35K','note':''},
                {'rank':'高级产品经理','range':'35K-55K','note':''},
                {'rank':'产品总监','range':'55K-80K','note':''}
            ]
        },
        'skills': {
            'hard_skills': [
                '产品设计工具：Figma / Sketch / Axure',
                '数据分析：SQL / Excel / Python基础',
                '项目管理工具：Jira / Notion / OmniPlan',
                '技术理解：了解前后端基础、API设计'
            ],
            'soft_skills': [
                '逻辑思维与抽象能力',
                '跨部门沟通协调能力',
                '用户同理心与需求洞察力',
                '项目推动与时间管理能力'
            ]
        },
        'references': [
            '[1] BOSS直聘. 2026年互联网行业薪酬报告[EB/OL]. https://www.zhipin.com, 2026-06.',
            '[2] 猎聘. 产品经理岗位薪资趋势[EB/OL]. https://www.liepin.com, 2026-06.',
            '[3] 拉勾网. 人工智能行业人才需求白皮书[EB/OL]. https://www.lagou.com, 2026-06.'
        ]
    }
    print(json.dumps(sample, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--sample':
        print_sample()
    elif len(sys.argv) >= 3:
        generate(sys.argv[1], sys.argv[2])
    else:
        print('Usage: python generate_report.py <input.json> <output.pdf>')
        print('       python generate_report.py --sample')
