"""
文档分析器主类

整合三个核心分析模块：
1. 事实核查器 (FactChecker)
2. 结构匹配器 (StructureMatcher)  
3. 质量评估器 (QualityEvaluator)

提供统一的文档分析接口，支持：
- 完整分析流程（结构+事实+质量）
- 自定义分析流程
- 批量文档分析
- 结果报告生成

Usage:
    # 完整分析
    analyzer = DocumentAnalyzer(deepseek_client, mcp_client)
    report = await analyzer.analyze(document_text, template_text)
    
    # 自定义分析
    result = await analyzer.analyze_custom(
        text,
        checks=['fact_check', 'quality'],
        template=None
    )
"""

import json
from typing import List, Dict, Any, Optional, Union, Callable, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
from pathlib import Path

from loguru import logger

from ..deepseek_client import DeepSeekClient
from ..mcp_client import TencentDocMCPClient, Comment, DocumentInfo
from .fact_checker import FactChecker, FactCheckResult, check_facts
from .structure_matcher import StructureMatcher, StructureMatchResult, match_structure
from .quality_evaluator import QualityEvaluator, QualityReport, evaluate_quality


class AnalysisType(Enum):
    """分析类型枚举"""
    FULL = "full"                           # 完整分析
    FACT_CHECK_ONLY = "fact_check"          # 仅事实核查
    STRUCTURE_ONLY = "structure"            # 仅结构匹配
    QUALITY_ONLY = "quality"                # 仅质量评估
    CUSTOM = "custom"                       # 自定义


@dataclass
class AnalysisConfig:
    """
    分析配置
    
    Attributes:
        analysis_type: 分析类型
        enable_fact_check: 启用事实核查
        enable_structure_match: 启用结构匹配
        enable_quality_eval: 启用质量评估
        fact_check_config: 事实核查配置
        structure_match_config: 结构匹配配置
        quality_eval_config: 质量评估配置
        batch_size: 批量处理大小
        max_concurrency: 最大并发数
        timeout: 超时时间
    """
    analysis_type: AnalysisType = AnalysisType.FULL
    enable_fact_check: bool = True
    enable_structure_match: bool = True
    enable_quality_eval: bool = True
    fact_check_config: Dict[str, Any] = field(default_factory=dict)
    structure_match_config: Dict[str, Any] = field(default_factory=dict)
    quality_eval_config: Dict[str, Any] = field(default_factory=dict)
    batch_size: int = 5
    max_concurrency: int = 3
    timeout: int = 300
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisConfig':
        """从字典创建配置"""
        config = cls()
        if 'analysis_type' in data:
            config.analysis_type = AnalysisType(data['analysis_type'])
        if 'enable_fact_check' in data:
            config.enable_fact_check = data['enable_fact_check']
        if 'enable_structure_match' in data:
            config.enable_structure_match = data['enable_structure_match']
        if 'enable_quality_eval' in data:
            config.enable_quality_eval = data['enable_quality_eval']
        if 'fact_check_config' in data:
            config.fact_check_config = data['fact_check_config']
        if 'structure_match_config' in data:
            config.structure_match_config = data['structure_match_config']
        if 'quality_eval_config' in data:
            config.quality_eval_config = data['quality_eval_config']
        if 'batch_size' in data:
            config.batch_size = data['batch_size']
        if 'max_concurrency' in data:
            config.max_concurrency = data['max_concurrency']
        if 'timeout' in data:
            config.timeout = data['timeout']
        return config


@dataclass
class AnalysisResult:
    """
    分析结果
    
    Attributes:
        document_id: 文档ID
        document_title: 文档标题
        analysis_type: 分析类型
        timestamp: 分析时间戳
        fact_check_results: 事实核查结果
        structure_match_result: 结构匹配结果
        quality_report: 质量评估报告
        summary: 分析摘要
        recommendations: 改进建议
        metadata: 元数据
    """
    document_id: str = ""
    document_title: str = ""
    analysis_type: AnalysisType = AnalysisType.FULL
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    fact_check_results: List[FactCheckResult] = field(default_factory=list)
    structure_match_result: Optional[StructureMatchResult] = None
    quality_report: Optional[QualityReport] = None
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "analysis_type": self.analysis_type.value,
            "timestamp": self.timestamp,
            "fact_check_results": [r.to_dict() for r in self.fact_check_results],
            "structure_match_result": self.structure_match_result.to_dict() if self.structure_match_result else None,
            "quality_report": self.quality_report.to_dict() if self.quality_report else None,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "metadata": self.metadata
        }
    
    def to_markdown(self) -> str:
        """转换为 Markdown 报告"""
        md = f"""# 文档分析报告

**文档**: {self.document_title or '未命名'}  
**分析类型**: {self.analysis_type.value}  
**分析时间**: {self.timestamp}

## 分析摘要

{self.summary}

"""
        
        # 事实核查部分
        if self.fact_check_results:
            md += "## 事实核查结果\n\n"
            for i, result in enumerate(self.fact_check_results[:10], 1):  # 最多显示10条
                status_icon = {
                    "confirmed": "✅",
                    "disputed": "⚠️",
                    "unverified": "❓",
                    "incorrect": "❌",
                    "partial": "〽️"
                }.get(result.verification_status.value, "❓")
                
                md += f"{i}. {status_icon} **{result.original_text}**\n"
                md += f"   - 状态: {result.verification_status.value}\n"
                md += f"   - 置信度: {result.confidence:.0%}\n"
                if result.suggestion:
                    md += f"   - 建议: {result.suggestion}\n"
                md += "\n"
        
        # 结构匹配部分
        if self.structure_match_result:
            md += "## 结构匹配结果\n\n"
            md += f"**整体匹配度**: {self.structure_match_result.overall_score:.1%}\n\n"
            
            if self.structure_match_result.section_matches:
                md += "### 章节匹配详情\n\n"
                for match in self.structure_match_result.section_matches[:15]:  # 最多显示15条
                    status_icon = {
                        "matched": "✅",
                        "missing": "❌",
                        "extra": "⚠️",
                        "misplaced": "📍",
                        "partial": "〽️",
                        "unknown": "❓"
                    }.get(match.status.value, "❓")
                    
                    md += f"{status_icon} **{match.template_section.title}**\n"
                    md += f"   - 状态: {match.status.value}\n"
                    md += f"   - 相似度: {match.similarity:.1%}\n"
                    if match.issues:
                        md += f"   - 问题: {match.issues[0]}\n"
                    md += "\n"
        
        # 质量评估部分
        if self.quality_report:
            md += "## 质量评估结果\n\n"
            md += f"**总体评分**: {self.quality_report.overall_score:.1f}/100\n"
            md += f"**质量等级**: {self.quality_report.overall_level.value.upper()}\n\n"
            
            if self.quality_report.dimension_scores:
                md += "### 各维度评分\n\n"
                md += "| 维度 | 得分 | 等级 |\n"
                md += "|------|------|------|\n"
                
                for ds in self.quality_report.dimension_scores:
                    md += f"| {ds.dimension.value} | {ds.score:.1f} | {ds.level.value} |\n"
                
                md += "\n"
        
        # 改进建议
        if self.recommendations:
            md += "## 改进建议\n\n"
            for i, rec in enumerate(self.recommendations, 1):
                md += f"{i}. {rec}\n"
            md += "\n"
        
        md += "---\n*报告生成时间: " + datetime.now().isoformat() + "*\n"
        
        return md


class DocumentAnalyzer:
    """
    文档分析器主类
    
    整合三个核心分析模块，提供统一的文档分析接口。
    
    Attributes:
        deepseek_client: DeepSeek API 客户端
        mcp_client: 腾讯文档 MCP 客户端
        fact_checker: 事实核查器
        structure_matcher: 结构匹配器
        quality_evaluator: 质量评估器
        config: 分析器配置
    """
    
    def __init__(
        self,
        deepseek_client: DeepSeekClient,
        mcp_client: Optional[TencentDocMCPClient] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化文档分析器
        
        Args:
            deepseek_client: DeepSeek API 客户端（必需）
            mcp_client: 腾讯文档 MCP 客户端（可选）
            config: 分析器配置（可选）
        """
        self.deepseek_client = deepseek_client
        self.mcp_client = mcp_client
        self.config = config or {}
        
        # 初始化三个核心分析器
        self.fact_checker = FactChecker(
            deepseek_client=deepseek_client,
            search_client=None,  # 暂时不使用搜索
            config=self.config.get('fact_check_config', {})
        )
        
        self.structure_matcher = StructureMatcher(
            deepseek_client=deepseek_client,
            config=self.config.get('structure_match_config', {})
        )
        
        self.quality_evaluator = QualityEvaluator(
            deepseek_client=deepseek_client,
            config=self.config.get('quality_eval_config', {})
        )
        
        logger.info("DocumentAnalyzer initialized")
    
    async def analyze(
        self,
        document_text: str,
        template_text: Optional[str] = None,
        document_id: str = "",
        document_title: str = "",
        context: Optional[Dict[str, Any]] = None,
        config: Optional[AnalysisConfig] = None
    ) -> AnalysisResult:
        """
        执行完整的文档分析
        
        这是主要入口方法，执行完整的分析流程（事实核查+结构匹配+质量评估）。
        
        Args:
            document_text: 文档内容
            template_text: 模板内容（可选）
            document_id: 文档ID
            document_title: 文档标题
            context: 上下文信息
            config: 分析配置
            
        Returns:
            分析结果
        """
        logger.info(f"Starting document analysis: {document_title or 'untitled'}")
        
        # 使用默认配置
        if config is None:
            config = AnalysisConfig()
        
        # 构建上下文
        analysis_context = context or {}
        analysis_context.update({
            'document_id': document_id,
            'document_title': document_title,
            'analysis_type': config.analysis_type.value
        })
        
        # 执行各项分析（并行）
        tasks = []
        
        # 事实核查
        if config.enable_fact_check:
            tasks.append(self._run_fact_check(document_text, analysis_context))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0)))  # 占位
        
        # 结构匹配
        if config.enable_structure_match and template_text:
            tasks.append(self._run_structure_match(document_text, template_text, analysis_context))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0)))  # 占位
        
        # 质量评估
        if config.enable_quality_eval:
            tasks.append(self._run_quality_eval(document_text, analysis_context))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0)))  # 占位
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        fact_check_results = []
        structure_match_result = None
        quality_report = None
        
        if config.enable_fact_check and not isinstance(results[0], Exception):
            fact_check_results = results[0]
        elif isinstance(results[0], Exception):
            logger.error(f"Fact check failed: {results[0]}")
        
        if config.enable_structure_match and template_text and not isinstance(results[1], Exception):
            structure_match_result = results[1]
        elif isinstance(results[1], Exception):
            logger.error(f"Structure match failed: {results[1]}")
        
        if config.enable_quality_eval and not isinstance(results[2], Exception):
            quality_report = results[2]
        elif isinstance(results[2], Exception):
            logger.error(f"Quality eval failed: {results[2]}")
        
        # 生成摘要
        summary = self._generate_summary(
            fact_check_results,
            structure_match_result,
            quality_report
        )
        
        # 生成改进建议
        recommendations = self._generate_recommendations(
            fact_check_results,
            structure_match_result,
            quality_report
        )
        
        # 构建结果
        result = AnalysisResult(
            document_id=document_id,
            document_title=document_title,
            analysis_type=config.analysis_type,
            fact_check_results=fact_check_results if fact_check_results else [],
            structure_match_result=structure_match_result,
            quality_report=quality_report,
            summary=summary,
            recommendations=recommendations,
            metadata={
                'document_length': len(document_text),
                'has_template': template_text is not None,
                'analysis_config': config.to_dict()
            }
        )
        
        logger.info(f"Document analysis completed: {document_title or 'untitled'}")
        return result
    
    async def _run_fact_check(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> List[FactCheckResult]:
        """运行事实核查"""
        logger.debug("Running fact check")
        return await self.fact_checker.check(text, context)
    
    async def _run_structure_match(
        self,
        document_text: str,
        template_text: str,
        context: Dict[str, Any]
    ) -> StructureMatchResult:
        """运行结构匹配"""
        logger.debug("Running structure match")
        return await self.structure_matcher.match(
            document_text,
            template_text,
            context
        )
    
    async def _run_quality_eval(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> QualityReport:
        """运行质量评估"""
        logger.debug("Running quality evaluation")
        return await self.quality_evaluator.evaluate(text, context)
    
    def _generate_summary(
        self,
        fact_check_results: Optional[List[FactCheckResult]],
        structure_match_result: Optional[StructureMatchResult],
        quality_report: Optional[QualityReport]
    ) -> str:
        """生成分析摘要"""
        summary_parts = []
        
        # 质量评估摘要
        if quality_report:
            summary_parts.append(
                f"质量评分: {quality_report.overall_score:.1f}/100 "
                f"({quality_report.overall_level.value.upper()})"
            )
        
        # 事实核查摘要
        if fact_check_results:
            total = len(fact_check_results)
            issues = sum(1 for r in fact_check_results 
                        if r.verification_status.value in ['disputed', 'incorrect', 'unverified'])
            summary_parts.append(f"事实核查: {total}项核查, {issues}项存疑")
        
        # 结构匹配摘要
        if structure_match_result:
            score = structure_match_result.overall_score
            summary_parts.append(f"结构匹配: {score:.1%}")
        
        return "\n".join(summary_parts) if summary_parts else "未生成摘要"
    
    def _generate_recommendations(
        self,
        fact_check_results: Optional[List[FactCheckResult]],
        structure_match_result: Optional[StructureMatchResult],
        quality_report: Optional[QualityReport]
    ) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 从质量报告中提取
        if quality_report and quality_report.priority_improvements:
            recommendations.extend(quality_report.priority_improvements[:3])
        
        # 从结构匹配中提取
        if structure_match_result:
            missing = [m for m in structure_match_result.section_matches 
                      if m.status.value == 'missing']
            if missing:
                recommendations.append(f"缺少{len(missing)}个必需章节，建议补充")
        
        # 从事实核查中提取
        if fact_check_results:
            issues = [r for r in fact_check_results 
                     if r.verification_status.value in ['incorrect', 'disputed']]
            if issues:
                recommendations.append(f"发现{len(issues)}处事实性问题，建议核实修改")
        
        return recommendations[:5]  # 最多返回5条
    
    async def analyze_custom(
        self,
        document_text: str,
        checks: List[str],
        template_text: Optional[str] = None,
        **kwargs
    ) -> AnalysisResult:
        """
        执行自定义分析
        
        Args:
            document_text: 文档内容
            checks: 检查项目列表 ['fact_check', 'structure', 'quality']
            template_text: 模板内容（结构匹配时需要）
            **kwargs: 其他参数
            
        Returns:
            分析结果
        """
        config = AnalysisConfig(
            analysis_type=AnalysisType.CUSTOM,
            enable_fact_check='fact_check' in checks,
            enable_structure_match='structure' in checks and template_text is not None,
            enable_quality_eval='quality' in checks
        )
        
        return await self.analyze(
            document_text=document_text,
            template_text=template_text if 'structure' in checks else None,
            config=config,
            **kwargs
        )
    
    async def analyze_batch(
        self,
        documents: List[Dict[str, Any]],
        config: Optional[AnalysisConfig] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[AnalysisResult]:
        """
        批量分析文档
        
        Args:
            documents: 文档列表，每个文档是包含 text, id, title 等字段的字典
            config: 分析配置
            progress_callback: 进度回调函数 (current, total, message)
            
        Returns:
            分析结果列表
        """
        if config is None:
            config = AnalysisConfig()
        
        total = len(documents)
        results = []
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(config.max_concurrency)
        
        async def analyze_with_semaphore(doc: Dict[str, Any], index: int) -> AnalysisResult:
            async with semaphore:
                try:
                    if progress_callback:
                        progress_callback(index + 1, total, f"Analyzing: {doc.get('title', 'untitled')}")
                    
                    result = await self.analyze(
                        document_text=doc.get('text', ''),
                        template_text=doc.get('template'),
                        document_id=doc.get('id', ''),
                        document_title=doc.get('title', ''),
                        context=doc.get('context'),
                        config=config
                    )
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Failed to analyze document {doc.get('id')}: {e}")
                    # 返回错误结果
                    return AnalysisResult(
                        document_id=doc.get('id', ''),
                        document_title=doc.get('title', ''),
                        summary=f"分析失败: {str(e)}",
                        recommendations=["请重试或联系技术支持"]
                    )
        
        # 创建所有任务
        tasks = [
            analyze_with_semaphore(doc, i)
            for i, doc in enumerate(documents)
        ]
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks)
        
        if progress_callback:
            progress_callback(total, total, "Batch analysis completed")
        
        return results
    
    async def analyze_from_tencent_doc(
        self,
        file_id: str,
        template_file_id: Optional[str] = None,
        config: Optional[AnalysisConfig] = None
    ) -> AnalysisResult:
        """
        从腾讯文档分析
        
        从腾讯文档读取内容，进行分析，并将结果以批注形式添加到原文档。
        
        Args:
            file_id: 腾讯文档文件ID
            template_file_id: 模板文档文件ID（可选）
            config: 分析配置
            
        Returns:
            分析结果
        """
        if self.mcp_client is None:
            raise ValueError("MCP client is required for Tencent Doc analysis")
        
        if config is None:
            config = AnalysisConfig()
        
        logger.info(f"Analyzing Tencent Doc: {file_id}")
        
        # 读取文档内容
        try:
            document_text = await self.mcp_client.get_document_content(file_id)
            document_info = None  # TODO: 获取文档信息
        except Exception as e:
            logger.error(f"Failed to read document {file_id}: {e}")
            raise
        
        # 读取模板内容（如果需要）
        template_text = None
        if config.enable_structure_match and template_file_id:
            try:
                template_text = await self.mcp_client.get_document_content(template_file_id)
            except Exception as e:
                logger.warning(f"Failed to read template {template_file_id}: {e}")
        
        # 执行分析
        result = await self.analyze(
            document_text=document_text,
            template_text=template_text,
            document_id=file_id,
            document_title=document_info.title if document_info else "",
            config=config
        )
        
        # 添加批注到腾讯文档
        if self.mcp_client:
            await self._add_annotations_to_doc(file_id, result)
        
        return result
    
    async def _add_annotations_to_doc(
        self,
        file_id: str,
        result: AnalysisResult
    ):
        """
        将分析结果以批注形式添加到腾讯文档
        
        Args:
            file_id: 腾讯文档文件ID
            result: 分析结果
        """
        if not self.mcp_client:
            return
        
        logger.info(f"Adding annotations to document: {file_id}")
        
        comments = []
        
        # 添加事实核查批注
        for fc_result in result.fact_check_results:
            if fc_result.verification_status.value in ['incorrect', 'disputed', 'unverified']:
                comment = Comment(
                    content=f"[事实核查-{fc_result.verification_status.value}] {fc_result.suggestion}",
                    position=fc_result.position,
                    quote_text=fc_result.original_text,
                    comment_type="warning"
                )
                comments.append(comment)
        
        # 添加结构匹配批注
        if result.structure_match_result:
            for match in result.structure_match_result.section_matches:
                if match.status.value in ['missing', 'misplaced']:
                    comment = Comment(
                        content=f"[结构-{match.status.value}] {match.suggestions[0] if match.suggestions else ''}",
                        position={},
                        quote_text=match.template_section.title,
                        comment_type="suggestion"
                    )
                    comments.append(comment)
        
        # 添加质量评估批注
        if result.quality_report and result.quality_report.priority_improvements:
            for improvement in result.quality_report.priority_improvements[:3]:  # 最多3条
                comment = Comment(
                    content=f"[质量改进] {improvement}",
                    position={},
                    comment_type="suggestion"
                )
                comments.append(comment)
        
        # 批量添加批注
        if comments:
            try:
                await self.mcp_client.add_comments_batch(file_id, comments)
                logger.info(f"Added {len(comments)} annotations to document {file_id}")
            except Exception as e:
                logger.error(f"Failed to add annotations: {e}")
    
    def save_report(
        self,
        result: AnalysisResult,
        output_path: str,
        format: str = "markdown"
    ):
        """
        保存分析报告
        
        Args:
            result: 分析结果
            output_path: 输出文件路径
            format: 输出格式 (markdown, json, html)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "markdown":
            content = result.to_markdown()
            output_path = output_path.with_suffix('.md')
        elif format == "json":
            content = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
            output_path = output_path.with_suffix('.json')
        elif format == "html":
            # TODO: 实现 HTML 格式
            content = self._convert_to_html(result)
            output_path = output_path.with_suffix('.html')
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Report saved to: {output_path}")
        return str(output_path)
    
    def _convert_to_html(self, result: AnalysisResult) -> str:
        """转换为 HTML 格式（简化版）"""
        md_content = result.to_markdown()
        # 这里可以使用 markdown 库转换为 HTML
        # 简化实现，直接返回带样式的 HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>文档分析报告 - {result.document_title or '未命名'}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
        h1 {{ color: #333; border-bottom: 2px solid #007acc; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        h3 {{ color: #666; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: 'Consolas', monospace; }}
        pre {{ background: #f8f8f8; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #f2f2f2; font-weight: bold; }}
        .highlight {{ background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0; }}
    </style>
</head>
<body>
    {self._markdown_to_html(md_content)}
</body>
</html>"""
        return html
    
    def _markdown_to_html(self, markdown: str) -> str:
        """简化的 Markdown 到 HTML 转换"""
        # 这里应该使用专门的库，简化实现
        # 仅处理基本的 Markdown 语法
        html = markdown
        
        # 标题
        html = html.replace('## ', '<h2>').replace('\n', '</h2>\n', 1)
        
        # 简单返回
        return f"<pre>{html}</pre>"


# 便捷函数

async def analyze_document(
    document_text: str,
    deepseek_client: DeepSeekClient,
    template_text: Optional[str] = None,
    mcp_client: Optional[TencentDocMCPClient] = None,
    **kwargs
) -> AnalysisResult:
    """
    便捷函数：快速分析文档
    
    Args:
        document_text: 文档内容
        deepseek_client: DeepSeek 客户端
        template_text: 模板内容（可选）
        mcp_client: MCP 客户端（可选）
        **kwargs: 其他参数
        
    Returns:
        分析结果
    """
    analyzer = DocumentAnalyzer(deepseek_client, mcp_client)
    return await analyzer.analyze(
        document_text=document_text,
        template_text=template_text,
        **kwargs
    )
