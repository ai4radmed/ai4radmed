-- oidc_auth.lua (DEBUG MODE 15 - COOKIE STORAGE + UNIQUE NAME)
local openidc = require("resty.openidc")

local function validate()
    ngx.log(ngx.ERR, "[[ DEBUG-OIDC ]] ----------------------------------------------------------------")
    ngx.log(ngx.ERR, "[[ DEBUG-OIDC ]] STEP 1: validate() called for URI: " .. ngx.var.uri)
    
    local client_id = os.getenv("OIDC_CLIENT_ID")
    local client_secret = os.getenv("OIDC_CLIENT_SECRET")
    local cookie_secret = os.getenv("OIDC_COOKIE_SECRET") or "v0123456789012345678901234567890"
    
    local discovery_url = "http://ai4radmed-keycloak:8080/realms/ai4radmed/.well-known/openid-configuration"

    -- [Fix] Dynamic Redirect URI
    local target_scheme = ngx.var.scheme
    if target_scheme == "http" and ngx.var.http_x_forwarded_proto == "https" then
        target_scheme = "https"
    end
    
    local redirect_uri = target_scheme .. "://" .. ngx.var.host .. "/redirect_uri"
    ngx.log(ngx.ERR, "[[ DEBUG-OIDC ]] Redirect URI: " .. redirect_uri)

    -- [DEBUG] Cookie Check
    local cookie_header = ngx.var.http_cookie or ""
    ngx.log(ngx.ERR, "[[ DEBUG-OIDC ]] Incoming Cookies: " .. cookie_header)
    
    local session_opts = {
        secret = cookie_secret,
        storage = "cookie", -- Use cookie storage for maximum cross-worker reliability
        name = "ai4radmed_session", -- Specific unique name
        cookie = {
            path = "/",
            secure = true, -- REQUIRED for SameSite=None
            samesite = "None", -- Permissive for cross-subdomain redirect
            http_only = true,
        },
    }

    local opts = {
        redirect_uri = redirect_uri,
        discovery = discovery_url,
        client_id = client_id,
        client_secret = client_secret,
        scope = "openid email profile",

        token_endpoint = "http://ai4radmed-keycloak:8080/realms/ai4radmed/protocol/openid-connect/token",
        userinfo_endpoint = "http://ai4radmed-keycloak:8080/realms/ai4radmed/protocol/openid-connect/userinfo",
        jwks_uri = "http://ai4radmed-keycloak:8080/realms/ai4radmed/protocol/openid-connect/certs",
        revocation_endpoint = "http://ai4radmed-keycloak:8080/realms/ai4radmed/protocol/openid-connect/revoke",
        
        logout_path = "/logout",
        redirect_after_logout_uri = "/",
        
        accept_bearer_token = true,
        iat_slack = 600,
        ssl_verify = "no",
        
        -- session_contents = { id_token = true, access_token = true } 
    }
    
    ngx.log(ngx.ERR, "[[ DEBUG-OIDC ]] STEP 2: authenticate...")
    local res, err = openidc.authenticate(opts, nil, nil, session_opts)
    
    if err then
        ngx.log(ngx.ERR, "[[ DEBUG-OIDC ]] STEP 3 ERROR: " .. (err or "unknown"))
        ngx.status = 500
        ngx.header.content_type = "text/html"
        ngx.say("<html><body><h1>Auth Error</h1><p>" .. (err or "unknown") .. "</p><p>Check if cookies are blocked.</p></body></html>")
        ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
    end

    if not res then
         ngx.log(ngx.ERR, "[[ DEBUG-OIDC ]] STEP 4: Redirecting...")
    else
         ngx.log(ngx.ERR, "[[ DEBUG-OIDC ]] STEP 5: SUCCESS! User: " .. (res.id_token and res.id_token.preferred_username or "unknown"))
         
         if res.id_token then
             ngx.req.set_header("X-User-Email", res.id_token.email or "")
         end
         
         if ngx.var.uri == "/redirect_uri" then
             return ngx.redirect("/")
         end
    end
end

return {
    validate = validate
}
