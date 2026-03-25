    # 继续实现辅助方法
    
    def _parse_section_from_dict(
        self,
        data: Dict[str, Any],
        level: int = 0
    ) -> Section:
        """从字典解析章节"""
        
        section = Section(
            title=data.get("title", "Untitled"),
            type=SectionType(data.get("type", "custom")),
            level=level,
            order=data.get("order", 0),
            content_summary=data.get("description", data.get("summary", "")),
            required=data.get("required", True),
            metadata=data.get("metadata", {})
        )
        
        # 解析子章节
        children_data = data.get("children", data.get("sections", []))
        for child_data in children_data:
            child_section = self._parse_section_from_dict(
                child_data,
                level=level + 1
            )
            section.children.append(child_section)
        
        return section
    
    def _fallback_parse(
        self,
        text: str,
        is_template: bool
    ) -> Section:
        """
        回退解析方法
        
        当 LLM 解析失败时，使用简单的启发式规则解析。
        """
        root = Section(
            title="Root",
            type=SectionType.CUSTOM,
            level=0
        )
        
        # 简单的正则匹配标题
        # 匹配 Markdown 标题、中文序号等
        patterns = [
            r'^(#{1,6})\s+(.+)$',  # Markdown 标题
            r'^(\d+[\.、])\s*(.+)$',  # 数字序号
            r'^([一二三四五六七八九十]+[、.])\s*(.+)$',  # 中文序号
            r'^第([一二三四五六七八九十]+|[\d]+)章\s*(.*)$',  # 第X章
            r'^第([一二三四五六七八九十]+|[\d]+)节\s*(.*)$',  # 第X节
        ]
        
        current_level = 1
        section_stack: List[Section] = [root]
        
        lines = text.split('\n')
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            matched = False
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    # 提取标题
                    if pattern.startswith(r'^(#'):
                        # Markdown 标题
                        hashes = match.group(1)
                        title = match.group(2).strip()
                        level = len(hashes)
                    elif '章' in pattern or '节' in pattern:
                        title = match.group(2).strip() or f"第{match.group(1)}章"
                        level = 1 if '章' in pattern else 2
                    else:
                        title = match.group(2).strip()
                        level = 2
                    
                    # 创建章节
                    section = Section(
                        title=title,
                        type=SectionType.CUSTOM,
                        level=level,
                        order=line_num,
                        metadata={"line_number": line_num}
                    )
                    
                    # 调整层级栈
                    while len(section_stack) > level:
                        section_stack.pop()
                    
                    # 添加到父章节
                    if section_stack:
                        section_stack[-1].children.append(section)
                    
                    section_stack.append(section)
                    matched = True
                    break
            
            # 如果没有匹配到标题，作为内容处理
            if not matched and section_stack[-1] != root:
                # 累积内容摘要
                current_section = section_stack[-1]
                current_section.content_summary += line + " "
                if len(current_section.content_summary) > 200:
                    current_section.content_summary = current_section.content_summary[:200] + "..."
        
        return root
    
    # 便捷函数


async def match_structure(
    document_text: str,
    template_text: str,
    deepseek_client: DeepSeekClient,
    context: Optional[Dict[str, Any]] = None
) -> StructureMatchResult:
    """
    便捷函数：快速匹配文档结构与模板
    
    Args:
        document_text: 文档内容
        template_text: 模板内容
        deepseek_client: DeepSeek 客户端
        context: 上下文
        
    Returns:
        匹配结果
    """
    matcher = StructureMatcher(deepseek_client)
    return await matcher.match(document_text, template_text, context)


async def parse_document_structure(
    text: str,
    deepseek_client: DeepSeekClient,
    context: Optional[Dict[str, Any]] = None
) -> Section:
    """
    便捷函数：快速解析文档结构
    
    Args:
        text: 文档内容
        deepseek_client: DeepSeek 客户端
        context: 上下文
        
    Returns:
        文档结构
    """
    matcher = StructureMatcher(deepseek_client)
    return await matcher.parse_document(text, context)
