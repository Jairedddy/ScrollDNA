import time

def scroll_page(page, step=120, delay=0.5, network_idle_timeout=2000):
    scroll_log = []
    
    # First, try to detect if this is a custom scroll implementation
    scroll_info = page.evaluate("""
        () => {
            const hasScrollbar = document.documentElement.scrollHeight > document.documentElement.clientHeight ||
                                 document.body.scrollHeight > document.body.clientHeight;
            
            // Check for common custom scroll indicators
            const bodyStyle = window.getComputedStyle(document.body);
            const htmlStyle = window.getComputedStyle(document.documentElement);
            const isFixed = bodyStyle.overflow === 'hidden' || htmlStyle.overflow === 'hidden';
            
            // Try to find scroll progress indicator
            const progressBar = document.querySelector('[class*="progress"], [id*="progress"], [class*="scroll"], [id*="scroll"]');
            
            return {
                hasScrollbar: hasScrollbar,
                isFixed: isFixed,
                bodyOverflow: bodyStyle.overflow,
                htmlOverflow: htmlStyle.overflow,
                hasProgressBar: !!progressBar,
                totalHeight: Math.max(
                    document.body.scrollHeight,
                    document.body.offsetHeight,
                    document.documentElement.clientHeight,
                    document.documentElement.scrollHeight,
                    document.documentElement.offsetHeight
                )
            };
        }
    """)
    
    total_height = scroll_info['totalHeight']
    is_custom_scroll = scroll_info['isFixed'] or not scroll_info['hasScrollbar']
    
    scroll_y = 0
    start_time = time.time()
    last_progress = 0
    
    # Get viewport height for calculating scroll steps
    viewport_height = page.evaluate("() => window.innerHeight || document.documentElement.clientHeight")
    
    if is_custom_scroll:
        # Use mouse wheel events for custom scroll implementations
        print("Detected custom scroll implementation - using mouse wheel events")
        
        # Calculate number of scroll steps needed - use a reasonable estimate
        # Formula: (total_height / step) * 2 + buffer
        num_steps = int((total_height / step) * 2) + 100  # More reasonable estimate
        stuck_count = 0
        max_stuck_count = 20  # Allow many more attempts before giving up
        consecutive_no_progress = 0
        zero_progress_count = 0  # Track how long we've been at 0% progress
        
        print(f"Starting scroll with {num_steps} steps (estimated total height: {total_height}px, step size: {step}px)")
        
        for i in range(num_steps):
            # Trigger wheel event (deltaY positive = scroll down)
            page.mouse.wheel(0, step)
            
            time.sleep(0.1)  # Wait for scroll animation
            
            # Check scroll progress by reading progress bar or scroll position
            progress = page.evaluate("""
                () => {
                    // Try multiple selectors for progress bar
                    const selectors = [
                        '[class*="progress"]',
                        '[id*="progress"]',
                        '[class*="scroll"]',
                        '[id*="scroll"]',
                        '[data-progress]',
                        '.progress-bar',
                        '#progress-bar'
                    ];
                    
                    let progressBar = null;
                    for (const selector of selectors) {
                        progressBar = document.querySelector(selector);
                        if (progressBar) break;
                    }
                    
                    if (progressBar) {
                        const style = window.getComputedStyle(progressBar);
                        const rect = progressBar.getBoundingClientRect();
                        
                        // Try width-based progress
                        const width = parseFloat(style.width) || rect.width || 0;
                        const parent = progressBar.parentElement;
                        if (parent) {
                            const parentStyle = window.getComputedStyle(parent);
                            const parentRect = parent.getBoundingClientRect();
                            const maxWidth = parseFloat(parentStyle.width) || parentRect.width || 100;
                            if (maxWidth > 0 && width > 0) {
                                const widthProgress = (width / maxWidth) * 100;
                                if (widthProgress >= 0 && widthProgress <= 100) return widthProgress;
                            }
                        }
                        
                        // Try transform-based progress (common in custom scroll)
                        const transform = style.transform;
                        if (transform && transform !== 'none') {
                            const matrix = transform.match(/matrix[^)]*\\)/);
                            if (matrix) {
                                const values = matrix[0].match(/-?\\d+\\.?\\d*/g);
                                if (values && values.length >= 5) {
                                    const translateY = parseFloat(values[5]);
                                    if (!isNaN(translateY)) {
                                        // This is a heuristic - adjust based on actual implementation
                                        return Math.abs(translateY) / 10;
                                    }
                                }
                            }
                        }
                        
                        // Try height-based progress
                        const height = parseFloat(style.height) || rect.height || 0;
                        if (parent) {
                            const parentHeight = parseFloat(window.getComputedStyle(parent).height) || parent.getBoundingClientRect().height || 100;
                            if (parentHeight > 0 && height > 0) {
                                const heightProgress = (height / parentHeight) * 100;
                                if (heightProgress >= 0 && heightProgress <= 100) return heightProgress;
                            }
                        }
                        
                        // Try data attribute
                        const dataProgress = progressBar.getAttribute('data-progress');
                        if (dataProgress) {
                            const val = parseFloat(dataProgress);
                            if (!isNaN(val) && val >= 0 && val <= 100) return val;
                        }
                    }
                    
                    // Fallback: try to get scroll position from window or custom scroll
                    const scrollPos = window.pageYOffset || window.scrollY || 
                                    document.documentElement.scrollTop || 
                                    document.body.scrollTop || 0;
                    const maxScroll = Math.max(
                        document.body.scrollHeight,
                        document.documentElement.scrollHeight
                    ) - (window.innerHeight || document.documentElement.clientHeight);
                    
                    if (maxScroll > 0) {
                        return (scrollPos / maxScroll) * 100;
                    }
                    
                    return 0;
                }
            """)
            
            now = time.time() - start_time
            scroll_y = int((progress / 100) * total_height) if progress > 0 else scroll_y + step
            
            scroll_log.append({
                "time": round(now, 3),
                "scrollY": scroll_y,
                "progress": round(progress, 2),
                "method": "wheel",
                "step": i
            })
            
            # Check if progress is stuck
            progress_changed = abs(progress - last_progress) >= 0.5
            
            if not progress_changed:
                consecutive_no_progress += 1
                stuck_count += 1
            else:
                consecutive_no_progress = 0
                stuck_count = 0
            
            # Track if we're stuck at 0% progress (indicates detection failure)
            if progress == 0:
                zero_progress_count += 1
            else:
                zero_progress_count = 0
            
            # Early exit if stuck at 0% for too long (progress detection likely failed)
            if zero_progress_count >= 30:
                print(f"Warning: Progress detection appears to be failing (stuck at 0% for {zero_progress_count} steps)")
                print("Attempting to continue with visual-based detection...")
                # Try to detect if we've actually scrolled by checking viewport changes
                viewport_check = page.evaluate("""
                    () => {
                        // Check if content has moved by comparing first visible element
                        const firstEl = document.elementFromPoint(window.innerWidth / 2, 10);
                        return firstEl ? firstEl.tagName : 'UNKNOWN';
                    }
                """)
                # If we've scrolled many times but progress is still 0, likely at end or detection broken
                if i > 50:
                    print(f"Scrolled {i} steps with no progress detected. Assuming completion or detection issue.")
                    break
            
            # Debug output every 20 steps
            if i % 20 == 0:
                print(f"Step {i}/{num_steps}: Progress={progress:.2f}%, Stuck count={stuck_count}, Zero progress count={zero_progress_count}")
            
            # Only break if we're at the end AND stuck for many attempts
            # Be very conservative - don't break early
            if progress >= 99.9:
                stuck_count += 1
                if stuck_count >= 20:  # Require many more confirmations at the end
                    print(f"Reached end of page (progress: {progress:.2f}%) after {i} steps")
                    break
            elif progress >= 98 and stuck_count >= max_stuck_count:
                # If we're very close to end and stuck, try harder
                print(f"Near end but stuck at {progress:.2f}%, trying alternative scroll methods...")
                # Try multiple scroll methods
                page.keyboard.press("PageDown")
                time.sleep(0.2)
                page.mouse.wheel(0, step * 2)  # Larger wheel scroll
                time.sleep(0.2)
                page.keyboard.press("ArrowDown")
                time.sleep(0.2)
                # Re-check progress
                progress = page.evaluate("""
                    () => {
                        const progressBar = document.querySelector('[class*="progress"], [id*="progress"]');
                        if (progressBar) {
                            const style = window.getComputedStyle(progressBar);
                            const width = parseFloat(style.width) || progressBar.getBoundingClientRect().width || 0;
                            const parent = progressBar.parentElement;
                            if (parent) {
                                const maxWidth = parseFloat(window.getComputedStyle(parent).width) || parent.getBoundingClientRect().width || 100;
                                if (maxWidth > 0 && width > 0) return (width / maxWidth) * 100;
                            }
                        }
                        return 0;
                    }
                """)
                stuck_count = 0  # Reset stuck count after alternative scroll methods
            
            last_progress = progress
            time.sleep(delay)
            
            # Update total height
            new_height = page.evaluate("""
                () => {
                    return Math.max(
                        document.body.scrollHeight,
                        document.body.offsetHeight,
                        document.documentElement.clientHeight,
                        document.documentElement.scrollHeight,
                        document.documentElement.offsetHeight
                    );
                }
            """)
            if new_height > total_height:
                old_total = total_height
                total_height = new_height
                # Extend num_steps if content grew significantly
                additional_steps = int((new_height - old_total) / step) + 20
                num_steps = max(num_steps, i + additional_steps)
                print(f"Content grew: {old_total} -> {new_height}, extending steps to {num_steps}")
            
            try:
                page.wait_for_load_state("networkidle", timeout=network_idle_timeout)
            except:
                pass
        
        # Final scroll attempts to ensure we reach the absolute end
        print("Performing final scrolls to reach end...")
        for final_scroll in range(30):  # More final scrolls
            page.mouse.wheel(0, step * 2)  # Larger scroll steps
            time.sleep(0.2)
            progress = page.evaluate("""
                () => {
                    const progressBar = document.querySelector('[class*="progress"], [id*="progress"]');
                    if (progressBar) {
                        const style = window.getComputedStyle(progressBar);
                        const width = parseFloat(style.width) || progressBar.getBoundingClientRect().width || 0;
                        const parent = progressBar.parentElement;
                        if (parent) {
                            const maxWidth = parseFloat(window.getComputedStyle(parent).width) || parent.getBoundingClientRect().width || 100;
                            if (maxWidth > 0 && width > 0) return (width / maxWidth) * 100;
                        }
                    }
                    return 0;
                }
            """)
            if progress >= 99.9:
                break
            time.sleep(0.1)
        
        # Log final progress
        final_progress = page.evaluate("""
            () => {
                const progressBar = document.querySelector('[class*="progress"], [id*="progress"]');
                if (progressBar) {
                    const style = window.getComputedStyle(progressBar);
                    const width = parseFloat(style.width) || progressBar.getBoundingClientRect().width || 0;
                    const parent = progressBar.parentElement;
                    if (parent) {
                        const maxWidth = parseFloat(window.getComputedStyle(parent).width) || parent.getBoundingClientRect().width || 100;
                        if (maxWidth > 0 && width > 0) return (width / maxWidth) * 100;
                    }
                }
                return 0;
            }
        """)
        print(f"Final scroll progress: {final_progress:.2f}%")
    else:
        # Standard scroll implementation
        print("Using standard scroll implementation")
        
        page.evaluate("""
            () => {
                document.documentElement.style.scrollBehavior = 'auto';
                if (document.body) {
                    document.body.style.scrollBehavior = 'auto';
                }
            }
        """)
        
        last_actual_scroll = 0
        stuck_count = 0
        
        while scroll_y < total_height:
            # Use multiple scroll methods for better compatibility
            page.evaluate(f"""
                () => {{
                    window.scrollTo({{ top: {scroll_y}, left: 0, behavior: 'instant' }});
                    window.scroll(0, {scroll_y});
                    document.documentElement.scrollTop = {scroll_y};
                    if (document.body) {{
                        document.body.scrollTop = {scroll_y};
                    }}
                }}
            """)
            
            time.sleep(0.1)
            
            actual_scroll = page.evaluate("() => window.pageYOffset || window.scrollY || document.documentElement.scrollTop || document.body.scrollTop")
            
            now = time.time() - start_time
            
            scroll_log.append({
                "time": round(now, 3),
                "scrollY": scroll_y,
                "actualScrollY": actual_scroll,
                "method": "standard"
            })
            
            if abs(actual_scroll - last_actual_scroll) < 5 and scroll_y > 0:
                stuck_count += 1
                if stuck_count > 3:
                    page.evaluate(f"""
                        () => {{
                            window.scrollTo(0, {scroll_y});
                            document.documentElement.scrollTop = {scroll_y};
                        }}
                    """)
                    time.sleep(0.2)
                    actual_scroll = page.evaluate("() => window.pageYOffset || window.scrollY || document.documentElement.scrollTop")
                    stuck_count = 0
            else:
                stuck_count = 0
            
            last_actual_scroll = actual_scroll
            
            new_height = page.evaluate("""
                () => {
                    return Math.max(
                        document.body.scrollHeight,
                        document.body.offsetHeight,
                        document.documentElement.clientHeight,
                        document.documentElement.scrollHeight,
                        document.documentElement.offsetHeight
                    );
                }
            """)
            if new_height > total_height:
                total_height = new_height
            
            try:
                page.wait_for_load_state("networkidle", timeout=network_idle_timeout)
            except:
                pass
            
            time.sleep(delay)
            scroll_y += step
            
            if actual_scroll >= total_height - 10:
                break
    
    return scroll_log