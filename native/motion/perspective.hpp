// Projective drag transform in the compositor's existing working colour space.
#pragma once
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/Shader.hpp>
#include <hyprutils/utils/ScopeGuard.hpp>

namespace hics::motion {
class Perspective {
  public:
    bool apply(SP<Render::IFramebuffer> input, SP<Render::IFramebuffer> output, CBox box, double tiltX, double tiltY) {
        if (!input || !input->getTexture() || !output || !shader()) return false;
        auto* renderer = g_pHyprRenderer.get();
        GLint viewport[4], scissor[4], vao, arrayBuffer, activeTexture, texture;
        GLboolean mask[4];
        GLfloat clearColor[4];
        glGetIntegerv(GL_VIEWPORT, viewport); glGetIntegerv(GL_SCISSOR_BOX, scissor);
        glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &vao); glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &arrayBuffer);
        glGetIntegerv(GL_ACTIVE_TEXTURE, &activeTexture);
        glActiveTexture(GL_TEXTURE0); glGetIntegerv(GL_TEXTURE_BINDING_2D, &texture);
        glGetBooleanv(GL_COLOR_WRITEMASK, mask);
        glGetFloatv(GL_COLOR_CLEAR_VALUE, clearColor);
        const bool blend = glIsEnabled(GL_BLEND), stencil = glIsEnabled(GL_STENCIL_TEST), clipping = glIsEnabled(GL_SCISSOR_TEST);
        auto binding = renderer->bindTempFB(output);
        Hyprutils::Utils::CScopeGuard restore([&] {
            renderer->setViewport(viewport[0],viewport[1],viewport[2],viewport[3]);
            renderer->blend(blend);
            Render::GL::g_pHyprOpenGL->setCapStatus(GL_STENCIL_TEST,stencil);
            Render::GL::g_pHyprOpenGL->setCapStatus(GL_SCISSOR_TEST,clipping);
            glScissor(scissor[0],scissor[1],scissor[2],scissor[3]);
            glColorMask(mask[0],mask[1],mask[2],mask[3]);
            glClearColor(clearColor[0],clearColor[1],clearColor[2],clearColor[3]);
            glBindVertexArray(vao); glBindBuffer(GL_ARRAY_BUFFER,arrayBuffer);
            glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D,texture); glActiveTexture(activeTexture);
        });
        renderer->setViewport(0,0,output->m_size.x,output->m_size.y);
        renderer->blend(false);
        Render::GL::g_pHyprOpenGL->setCapStatus(GL_STENCIL_TEST,false);
        renderer->disableScissor(); glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);
        glClearColor(0,0,0,0); glClear(GL_COLOR_BUFFER_BIT);
        Render::GL::g_pHyprOpenGL->useShader(m_shader);
        m_shader->setUniformInt(SHADER_TEX,0);
        glUniform2f(m_size,output->m_size.x,output->m_size.y);
        glUniform4f(m_box,box.x,output->m_size.y-box.y-box.h,box.w,box.h);
        glUniform2f(m_tilt,tiltX,tiltY);
        glActiveTexture(GL_TEXTURE0); input->getTexture()->bind();
        glBindVertexArray(m_shader->getUniformLocation(SHADER_SHADER_VAO));
        glDrawArrays(GL_TRIANGLE_STRIP,0,4);
        return glGetError() == GL_NO_ERROR;
    }
  private:
    bool shader() {
        if (m_shader) return true;
        if (m_attempted) return false;
        m_attempted = true;
        auto value = makeShared<CShader>();
        const std::string vertex = R"GLSL(#version 300 es
precision highp float;
in vec2 pos;
out vec2 uv;
uniform vec2 screenSize;
uniform vec4 box;
uniform vec2 tilt;
void main() {
    vec2 pixel = box.xy + pos * box.zw;
    uv = pixel / screenSize;
    vec2 local = (pos - 0.5) * box.zw;
    float cx = cos(tilt.x), sx = sin(tilt.x);
    float cy = cos(tilt.y), sy = sin(tilt.y);
    vec3 v = vec3(local.x, local.y * cx, local.y * sx);
    v = vec3(v.x * cy + v.z * sy, v.y, -v.x * sy + v.z * cy);
    float w = max(0.5, 1.0 - v.z / 1400.0);
    vec2 center = box.xy + box.zw * 0.5;
    vec2 ndc = (center * w + v.xy) * 2.0 / screenSize - vec2(w);
    gl_Position = vec4(ndc, 0.0, w);
}
)GLSL";
        const std::string fragment = R"GLSL(#version 300 es
precision highp float;
uniform sampler2D tex;
in vec2 uv;
out vec4 result;
void main() { result = texture(tex, uv); }
)GLSL";
        if (!value->createProgram(vertex,fragment,true,true)) return false;
        m_size=glGetUniformLocation(value->program(),"screenSize");
        m_box=glGetUniformLocation(value->program(),"box");
        m_tilt=glGetUniformLocation(value->program(),"tilt");
        m_shader=value;
        return true;
    }
    SP<CShader> m_shader;
    bool m_attempted=false;
    GLint m_size=-1,m_box=-1,m_tilt=-1;
};
}
