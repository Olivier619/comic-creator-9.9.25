import os
from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # 1. Setup: Upload template and panel image
            app_url = "http://127.0.0.1:5004"
            page.goto(app_url, wait_until='networkidle')

            template_path = os.path.abspath('jules-scratch/verification/template_with_boxes.png')
            page.locator('input[name="template_file"]').set_input_files(template_path)
            page.get_by_role('button', name='Télécharger la planche').click()

            drop_zones = page.locator('.panel-drop-zone')
            expect(drop_zones).to_have_count(3, timeout=10000)
            
            panel_path = os.path.abspath('jules-scratch/verification/panel_v2.png')
            page.locator('input[name="panel_files[]"]').set_input_files(panel_path)
            page.get_by_role('button', name='Télécharger les images').click()
            
            thumbnail = page.locator('#panel-thumbnails img')
            expect(thumbnail).to_be_visible(timeout=10000)

            # 2. Drop image into the first panel
            first_drop_zone = drop_zones.first
            thumbnail.drag_to(first_drop_zone)
            
            panel_img = first_drop_zone.locator('img')
            expect(panel_img).to_be_visible(timeout=5000)
            print("Image dropped into panel successfully.")

            # 3. Verify Panning
            initial_left = panel_img.evaluate('el => el.style.left')
            box = panel_img.bounding_box()
            page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
            page.mouse.down()
            page.mouse.move(box['x'] + box['width'] / 2 - 20, box['y'] + box['height'] / 2 - 20)
            page.mouse.up()
            
            expect(panel_img).not_to_have_css('left', initial_left)
            print("Panning verified: image position has changed.")

            # 4. Verify Zooming
            initial_width = panel_img.evaluate('el => el.clientWidth')
            panel_img.hover()
            page.mouse.wheel(0, -50) # Zoom in
            
            # Use a custom assertion to check if width has increased
            expect.poll(lambda: panel_img.evaluate('el => el.clientWidth') > initial_width, timeout=5000).to_be(True)
            print("Zooming verified: image width has increased.")

            # 5. Take a screenshot for visual confirmation
            screenshot_path = 'jules-scratch/verification/verification_pan_zoom.png'
            page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"An error occurred during verification: {e}")
            page.screenshot(path='jules-scratch/verification/error_pan_zoom.png')
        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()
